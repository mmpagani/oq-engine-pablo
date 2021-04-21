# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2021 GEM Foundation
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake. If not, see <http://www.gnu.org/licenses/>.

import numpy
import pandas

from openquake.baselib import hdf5, general, parallel
from openquake.commonlib import datastore
from openquake.calculators import base
from openquake.calculators.event_based_risk import EventBasedRiskCalculator

U8 = numpy.uint8
U16 = numpy.uint16
U32 = numpy.uint32
F32 = numpy.float32


def fix_dtype(dic, dtype, names):
    for name in names:
        dic[name] = dtype(dic[name])


def agg_damages(dstore, slc, monitor):
    """
    :returns: dict (agg_id, loss_id) -> [dmg1, dmg2, ...]
    """
    with dstore:
        df = dstore.read_df('agg_damage_table', ['agg_id', 'loss_id'], slc=slc)
        del df['event_id']
        agg = df.groupby(df.index).sum()
        dic = dict(zip(agg.index, agg.to_numpy()))
    return dic


def event_based_damage(df, param, monitor):
    """
    :param df: a DataFrame of GMFs with fields sid, eid, gmv_...
    :param param: a dictionary of parameters coming from the job.ini
    :param monitor: a Monitor instance
    :returns: damages as a dictionary (eid, kid) -> LD
    """
    mon_risk = monitor('computing risk', measuremem=False)
    dstore = datastore.read(param['hdf5path'])
    K = param['K']
    with monitor('reading data'):
        if hasattr(df, 'start'):  # it is actually a slice
            df = dstore.read_df('gmf_data', slc=df)
        assets_df = dstore.read_df('assetcol/array', 'ordinal')
        kids = (dstore['assetcol/kids'][:] if K
                else numpy.zeros(len(assets_df), U16))
        crmodel = monitor.read('crmodel')
    dmg_csq = crmodel.get_dmg_csq()
    L = len(crmodel.loss_types)
    D = len(crmodel.damage_states)
    ci = {dc: i + 1 for i, dc in enumerate(dmg_csq)}
    DC = len(ci) + 1
    with mon_risk:
        dddict = general.AccumDict(accum=numpy.zeros((L, DC), F32))  # eid, kid
        for taxo, asset_df in assets_df.groupby('taxonomy'):
            for sid, adf in asset_df.groupby('site_id'):
                gmf_df = df[df.sid == sid]
                if len(gmf_df) == 0:
                    continue
                out = crmodel.get_output(taxo, adf, gmf_df)
                eids = out['eids']
                aids = out['assets']['ordinal']
                for lti, lt in enumerate(out['loss_types']):
                    fractions = out[lt]
                    A, E, D = fractions.shape
                    ddd = numpy.zeros((A, E, DC), F32)
                    ddd[:, :, :D] = fractions
                    for a, asset in enumerate(out['assets']):
                        ddd[a] *= asset['number']
                        csq = crmodel.compute_csq(asset, fractions[a], lt)
                        for name, values in csq.items():
                            ddd[a, :, ci[name]] = values
                    tot = ddd.sum(axis=0)
                    for e, eid in enumerate(eids):
                        dddict[eid, K][lti] += tot[e]
                        if K:
                            for a, aid in enumerate(aids):
                                dddict[eid, kids[aid]][lti] += ddd[a, e]
    return to_dframe(dddict, ci, L)


def to_dframe(adic, ci, L):
    dic = general.AccumDict(accum=[])
    for (eid, kid), dd in sorted(adic.items()):
        for lti in range(L):
            dic['event_id'].append(eid)
            dic['agg_id'].append(kid)
            dic['loss_id'].append(lti)
            for sname, si in ci.items():
                dic[sname].append(dd[lti, si])
    fix_dtype(dic, U32, ['event_id'])
    fix_dtype(dic, U16, ['agg_id'])
    fix_dtype(dic, U8, ['loss_id'])
    fix_dtype(dic, F32, ci)
    return pandas.DataFrame(dic)


@base.calculators.add('event_based_damage')
class DamageCalculator(EventBasedRiskCalculator):
    """
    Damage calculator
    """
    core_task = event_based_damage
    is_stochastic = True
    precalc = 'event_based'
    accept_precalc = ['scenario', 'event_based',
                      'event_based_risk', 'event_based_damage']

    def execute(self):
        """
        Compute risk from GMFs or ruptures depending on what is stored
        """
        smap = parallel.Starmap(
            event_based_damage, self.gen_args(), h5=self.datastore.hdf5)
        smap.monitor.save('assets', self.assetcol.to_dframe())
        smap.monitor.save('crmodel', self.crmodel)
        return smap.reduce(self.combine)

    def combine(self, acc, res):
        """
        :param acc: unused
        :param res: DataFrame with fields (event_id, agg_id, loss_id, dmg1 ...)
        Combine the results and grows agg_damage_table with fields
        (event_id, agg_id, loss_id) and (dmg_0, dmg_1, dmg_2, ...)
        """
        if res is None:
            raise MemoryError('You ran out of memory!')
        with self.monitor('saving agg_damage_table', measuremem=True):
            for name in res.columns:
                dset = self.datastore['agg_damage_table/' + name]
                hdf5.extend(dset, res[name].to_numpy())
        return 1

    def post_execute(self, dummy):
        oq = self.oqparam
        len_table = len(self.datastore['agg_damage_table/event_id'])
        self.datastore.swmr_on()
        smap = parallel.Starmap(agg_damages, h5=self.datastore.hdf5)
        ct = oq.concurrent_tasks or 1
        for slc in general.split_in_slices(len_table, ct):
            smap.submit((self.datastore, slc))
        agg = smap.reduce()  # (agg_id, loss_id) -> cum_ddd
        alias = {dc: i for i, dc in enumerate(self.crmodel.get_dmg_csq())}
        dic = general.AccumDict(accum=[])
        for (k, li), dmgs in agg.items():
            dic['agg_id'].append(k)
            dic['loss_id'].append(li)
            for name, idx in alias.items():
                dic[name].append(dmgs[idx])
        fix_dtype(dic, U16, ['agg_id'])
        fix_dtype(dic, U8, ['loss_id'])
        fix_dtype(dic, F32, alias)
        self.datastore.create_dframe('dmg_csq', dic.items())
