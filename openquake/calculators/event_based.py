# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2015-2018 GEM Foundation
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
import os.path
import logging
import collections
import mock
import numpy

from openquake.baselib import hdf5, datastore
from openquake.baselib.python3compat import zip
from openquake.baselib.general import (
    AccumDict, block_splitter, split_in_slices, humansize, get_array)
from openquake.hazardlib.probability_map import ProbabilityMap
from openquake.hazardlib.stats import compute_pmap_stats
from openquake.risklib.riskinput import str2rsi
from openquake.baselib import parallel
from openquake.commonlib import calc, util, readinput
from openquake.calculators import base
from openquake.calculators.getters import GmfGetter, RuptureGetter
from openquake.calculators.classical import ClassicalCalculator

U8 = numpy.uint8
U16 = numpy.uint16
U32 = numpy.uint32
U64 = numpy.uint64
F32 = numpy.float32
F64 = numpy.float64
TWO32 = 2 ** 32
RUPTURES_PER_BLOCK = 200  # decided by MS


def weight(src):
    # heuristic weight
    return len(src.eb_ruptures)  # this is the best
    # return sum(ebr.multiplicity for ebr in src.eb_ruptures)


def get_events(ebruptures):
    """
    Extract an array of dtype stored_event_dt from a list of EBRuptures
    """
    events = []
    year = 0  # to be set later
    for ebr in ebruptures:
        for event in ebr.events:
            rec = (event['eid'], ebr.serial, ebr.grp_id, year, event['ses'],
                   event['sample'])
            events.append(rec)
    return numpy.array(events, readinput.stored_event_dt)


def max_gmf_size(ruptures_by_grp, get_rlzs_by_gsim,
                 samples_by_grp, num_imts):
    """
    :param ruptures_by_grp: dictionary grp_id -> EBRuptures
    :param rlzs_by_gsim: method grp_id -> {gsim: rlzs}
    :param samples_by_grp: dictionary grp_id -> samples
    :param num_imts: number of IMTs
    :returns:
        the size of the GMFs generated by the ruptures, by excess, if
        minimum_intensity is set
    """
    # ('rlzi', U16), ('sid', U32),  ('eid', U64), ('gmv', (F32, (len(imtls),)))
    nbytes = 2 + 4 + 8 + 4 * num_imts
    n = 0
    for grp_id, ebruptures in ruptures_by_grp.items():
        sample = 0
        samples = samples_by_grp[grp_id]
        for gsim, rlzs in get_rlzs_by_gsim(grp_id).items():
            for ebr in ebruptures:
                if samples > 1:
                    len_eids = [len(get_array(ebr.events, sample=s)['eid'])
                                for s in range(sample, sample + len(rlzs))]
                else:  # full enumeration
                    len_eids = [len(ebr.events['eid'])] * len(rlzs)
                for r, rlzi in enumerate(rlzs):
                    n += len(ebr.rupture.sctx.sids) * len_eids[r]
            sample += len(rlzs)
    return n * nbytes


def set_counts(dstore, dsetname):
    """
    :param dstore: a DataStore instance
    :param dsetname: name of dataset with a field `grp_id`
    :returns: a dictionary grp_id > counts
    """
    groups = dstore[dsetname]['grp_id']
    unique, counts = numpy.unique(groups, return_counts=True)
    dic = dict(zip(unique, counts))
    dstore.set_attrs(dsetname, by_grp=sorted(dic.items()))
    return dic


def set_random_years(dstore, name, investigation_time):
    """
    Set on the `events` dataset year labels sensitive to the
    SES ordinal and the investigation time.

    :param dstore: a DataStore instance
    :param name: name of the dataset ('events')
    :param investigation_time: investigation time
    """
    events = dstore[name].value
    years = numpy.random.choice(investigation_time, len(events)) + 1
    year_of = dict(zip(numpy.sort(events['eid']), years))  # eid -> year
    for event in events:
        event['year'] = year_of[event['eid']]
    dstore[name] = events


# ######################## GMF calculator ############################ #

def update_nbytes(dstore, key, array):
    nbytes = dstore.get_attr(key, 'nbytes', 0)
    dstore.set_attrs(key, nbytes=nbytes + array.nbytes)


def get_mean_curves(dstore):
    """
    Extract the mean hazard curves from the datastore, as a composite
    array of length nsites.
    """
    return dstore['hcurves/mean'].value

# ########################################################################## #


def compute_gmfs(sources_or_ruptures, src_filter,
                 rlzs_by_gsim, param, monitor):
    """
    Compute GMFs and optionally hazard curves
    """
    res = AccumDict(ruptures={})
    ruptures = []
    with monitor('building ruptures', measuremem=True):
        if isinstance(sources_or_ruptures, RuptureGetter):
            # the ruptures are read from the datastore
            grp_id = sources_or_ruptures.grp_id
            ruptures.extend(sources_or_ruptures)
            sitecol = src_filter  # this is actually a site collection
        else:
            # use the ruptures sampled in prefiltering
            grp_id = sources_or_ruptures[0].src_group_id
            for src in sources_or_ruptures:
                ruptures.extend(src.eb_ruptures)
            sitecol = src_filter.sitecol
    if ruptures:
        if not param['oqparam'].save_ruptures or isinstance(
                sources_or_ruptures, RuptureGetter):  # ruptures already saved
            res.events = get_events(ruptures)
        else:
            res['ruptures'] = {grp_id: ruptures}
        getter = GmfGetter(
            rlzs_by_gsim, ruptures, sitecol,
            param['oqparam'], param['min_iml'], param['samples'])
        res.update(getter.compute_gmfs_curves(monitor))
    return res


@base.calculators.add('event_based')
class EventBasedCalculator(base.HazardCalculator):
    """
    Event based PSHA calculator generating the ground motion fields and
    the hazard curves from the ruptures, depending on the configuration
    parameters.
    """
    core_task = compute_gmfs
    is_stochastic = True

    def gen_args(self, monitor):
        """
        :yields: the arguments for compute_gmfs_and_curves
        """
        oq = self.oqparam
        param = dict(
            oqparam=oq, min_iml=self.get_min_iml(oq),
            truncation_level=oq.truncation_level,
            imtls=oq.imtls, filter_distance=oq.filter_distance,
            ses_per_logic_tree_path=oq.ses_per_logic_tree_path)
        concurrent_tasks = oq.concurrent_tasks
        if oq.hazard_calculation_id:
            U = len(self.datastore.parent['ruptures'])
            logging.info('Found %d ruptures', U)
            parent = self.can_read_parent() or self.datastore
            samples_by_grp = self.csm_info.get_samples_by_grp()
            for slc in split_in_slices(U, concurrent_tasks or 1):
                for grp_id in self.rlzs_by_gsim_grp:
                    rlzs_by_gsim = self.rlzs_by_gsim_grp[grp_id]
                    ruptures = RuptureGetter(parent, slc, grp_id)
                    param['samples'] = samples_by_grp[grp_id]
                    yield ruptures, self.sitecol, rlzs_by_gsim, param, monitor
            return

        maxweight = self.csm.get_maxweight(weight, concurrent_tasks or 1)
        logging.info('Using maxweight=%d', maxweight)
        num_tasks = 0
        num_sources = 0
        for sm in self.csm.source_models:
            param['samples'] = sm.samples
            for sg in sm.src_groups:
                # ignore the sources not producing ruptures
                sg.sources = [src for src in sg.sources if src.eb_ruptures]
                if not sg.sources:
                    continue
                rlzs_by_gsim = self.rlzs_by_gsim_grp[sg.id]
                if sg.src_interdep == 'mutex':  # do not split
                    yield sg, self.src_filter, rlzs_by_gsim, param, monitor
                    num_tasks += 1
                    num_sources += len(sg.sources)
                    continue
                for block in block_splitter(sg.sources, maxweight, weight):
                    yield block, self.src_filter, rlzs_by_gsim, param, monitor
                    num_tasks += 1
                    num_sources += len(block)
        logging.info('Sent %d sources in %d tasks', num_sources, num_tasks)

    def zerodict(self):
        """
        Initial accumulator, a dictionary (grp_id, gsim) -> curves
        """
        if self.oqparam.hazard_calculation_id is None:
            self.csm_info = self.process_csm()
        else:
            self.datastore.parent = datastore.read(
                self.oqparam.hazard_calculation_id)
            self.csm_info = self.datastore.parent['csm_info']
        self.rlzs_by_gsim_grp = self.csm_info.get_rlzs_by_gsim_grp()
        self.L = len(self.oqparam.imtls.array)
        self.R = self.csm_info.get_num_rlzs()
        zd = AccumDict({r: ProbabilityMap(self.L) for r in range(self.R)})
        zd.eff_ruptures = AccumDict()
        self.grp_trt = self.csm_info.grp_by("trt")
        return zd

    def process_csm(self):  # called after split_all
        """
        Prefilter the composite source model and store the source_info
        """
        try:
            source_info = self.datastore['source_info']
        except KeyError:  # UCERF
            source_info = None
        self.src_filter, self.csm = self.filter_csm()
        rlzs_assoc = self.csm.info.get_rlzs_assoc()
        samples_by_grp = self.csm.info.get_samples_by_grp()
        gmf_size = 0
        for src in self.csm.get_sources():
            if hasattr(src, 'eb_ruptures'):  # except UCERF
                gmf_size += max_gmf_size(
                    {src.src_group_id: src.eb_ruptures},
                    rlzs_assoc.get_rlzs_by_gsim,
                    samples_by_grp, len(self.oqparam.imtls))
            # update source_info
            if source_info and hasattr(src, 'calc_times'):
                for srcid, nsites, eids, dt in src.calc_times:
                    info = source_info[srcid]
                    info['num_sites'] += nsites
                    info['calc_time'] += dt
                    info['num_split'] += 1
                    info['events'] += len(eids)
                    source_info[srcid] = info
                del src.calc_times
            # save the events always and the ruptures if oq.save_ruptures
            if hasattr(src, 'eb_ruptures'):
                self.save_ruptures(src.eb_ruptures)
        self.rupser.close()
        if gmf_size:
            self.datastore.set_attrs('events', max_gmf_size=gmf_size)
            msg = 'less than ' if self.get_min_iml(self.oqparam).sum() else ''
            logging.info('Estimating %s%s of GMFs',
                         msg, humansize(gmf_size))

        with self.monitor('store source_info', autoflush=True):
            acc = mock.Mock(eff_ruptures={
                grp.id: sum(src.num_ruptures for src in grp)
                for grp in self.csm.src_groups})
            self.store_source_info(acc)
        return self.csm.info

    def agg_dicts(self, acc, result):
        """
        :param acc: accumulator dictionary
        :param result: an AccumDict with events, ruptures, gmfs and hcurves
        """
        # in UCERF
        if hasattr(result, 'ruptures_by_grp'):
            for ruptures in result.ruptures_by_grp.values():
                self.save_ruptures(ruptures)
        elif hasattr(result, 'events_by_grp'):
            for grp_id in result.events_by_grp:
                events = result.events_by_grp[grp_id]
                self.datastore.extend('events', events)
        sav_mon = self.monitor('saving gmfs')
        agg_mon = self.monitor('aggregating hcurves')
        if 'gmdata' in result:
            self.gmdata += result['gmdata']
            data = result['gmfdata']
            with sav_mon:
                self.datastore.extend('gmf_data/data', data)
                # it is important to save the number of bytes while the
                # computation is going, to see the progress
                update_nbytes(self.datastore, 'gmf_data/data', data)
                for sid, start, stop in result['indices']:
                    self.indices[sid, 0].append(start + self.offset)
                    self.indices[sid, 1].append(stop + self.offset)
                self.offset += len(data)
                if self.offset >= TWO32:
                    raise RuntimeError(
                        'The gmf_data table has more than %d rows' % TWO32)
        imtls = self.oqparam.imtls
        with agg_mon:
            for key, poes in result.get('hcurves', {}).items():
                r, sid, imt = str2rsi(key)
                array = acc[r].setdefault(sid, 0).array[imtls(imt), 0]
                array[:] = 1. - (1. - array) * (1. - poes)
        sav_mon.flush()
        agg_mon.flush()
        self.datastore.flush()
        return acc

    def save_ruptures(self, ruptures):
        """
        Extend the 'events' dataset with the events from the given ruptures;
        also, save the ruptures if the flag `save_ruptures` is on.

        :param ruptures: a list of EBRuptures
        """
        if len(ruptures):
            with self.monitor('saving ruptures', autoflush=True):
                events = get_events(ruptures)
                dset = self.datastore.extend('events', events)
                if self.oqparam.save_ruptures:
                    self.rupser.save(ruptures, eidx=len(dset)-len(events))

    def check_overflow(self):
        """
        Raise a ValueError if the number of sites is larger than 65,536 or the
        number of IMTs is larger than 256 or the number of ruptures is larger
        than 4,294,967,296. The limits are due to the numpy dtype used to
        store the GMFs (gmv_dt). They could be relaxed in the future.
        """
        max_ = dict(sites=2**16, events=2**32, imts=2**8)
        try:
            events = len(self.datastore['events'])
        except KeyError:
            events = 0
        num_ = dict(sites=len(self.sitecol), events=events,
                    imts=len(self.oqparam.imtls))
        for var in max_:
            if num_[var] > max_[var]:
                raise ValueError(
                    'The event based calculator is restricted to '
                    '%d %s, got %d' % (max_[var], var, num_[var]))

    def execute(self):
        if self.oqparam.hazard_calculation_id:
            def saving_sources_by_task(allargs, dstore):
                return allargs
        else:
            from openquake.calculators.classical import saving_sources_by_task
        self.gmdata = {}
        self.offset = 0
        self.indices = collections.defaultdict(list)  # sid, idx -> indices
        acc = self.zerodict()
        with self.monitor('managing sources', autoflush=True):
            allargs = self.gen_args(self.monitor('classical'))
            iterargs = saving_sources_by_task(allargs, self.datastore)
            if isinstance(allargs, list):
                # there is a trick here: if the arguments are known
                # (a list, not an iterator), keep them as a list
                # then the Starmap will understand the case of a single
                # argument tuple and it will run in core the task
                iterargs = list(iterargs)
            if self.oqparam.ground_motion_fields is False:
                logging.info('Generating ruptures only')
            ires = parallel.Starmap(
                self.core_task.__func__, iterargs, self.monitor()
            ).submit_all()
        acc = ires.reduce(self.agg_dicts, acc)
        self.check_overflow()  # check the number of events
        base.save_gmdata(self, self.R)
        if self.indices:
            N = len(self.sitecol.complete)
            logging.info('Saving gmf_data/indices')
            with self.monitor('saving gmf_data/indices', measuremem=True,
                              autoflush=True):
                dset = self.datastore.create_dset(
                    'gmf_data/indices', hdf5.vuint32,
                    shape=(N, 2), fillvalue=None)
                for sid in self.sitecol.complete.sids:
                    dset[sid, 0] = self.indices[sid, 0]
                    dset[sid, 1] = self.indices[sid, 1]
        elif (self.oqparam.ground_motion_fields and
              'ucerf' not in self.oqparam.calculation_mode):
            raise RuntimeError('No GMFs were generated, perhaps they were '
                               'all below the minimum_intensity threshold')
        return acc

    def save_gmf_bytes(self):
        """Save the attribute nbytes in the gmf_data datasets"""
        ds = self.datastore
        for sm_id in ds['gmf_data']:
            ds.set_nbytes('gmf_data/' + sm_id)
        ds.set_nbytes('gmf_data')

    def init(self):
        self.rupser = calc.RuptureSerializer(self.datastore)

    def post_execute(self, result):
        """
        Save the SES collection
        """
        self.rupser.close()
        oq = self.oqparam
        N = len(self.sitecol.complete)
        L = len(oq.imtls.array)
        if oq.hazard_calculation_id is None:
            num_events = sum(set_counts(self.datastore, 'events').values())
            if num_events == 0:
                raise RuntimeError(
                    'No seismic events! Perhaps the investigation time is too '
                    'small or the maximum_distance is too small')
            if oq.save_ruptures:
                logging.info('Setting %d event years on %d ruptures',
                             num_events, self.rupser.nruptures)
            with self.monitor('setting event years', measuremem=True,
                              autoflush=True):
                numpy.random.seed(self.oqparam.ses_seed)
                set_random_years(self.datastore, 'events',
                                 int(self.oqparam.investigation_time))

        if oq.hazard_curves_from_gmfs:
            rlzs = self.csm_info.rlzs_assoc.realizations
            # compute and save statistics; this is done in process and can
            # be very slow if there are thousands of realizations
            weights = [rlz.weight for rlz in rlzs]
            # NB: in the future we may want to save to individual hazard
            # curves if oq.individual_curves is set; for the moment we
            # save the statistical curves only
            hstats = oq.hazard_stats()
            if len(hstats):
                logging.info('Computing statistical hazard curves')
                for statname, stat in hstats:
                    pmap = compute_pmap_stats(result.values(), [stat], weights)
                    arr = numpy.zeros((N, L), F32)
                    for sid in pmap:
                        arr[sid] = pmap[sid].array[:, 0]
                    self.datastore['hcurves/' + statname] = arr
                    if oq.poes:
                        P = len(oq.poes)
                        I = len(oq.imtls)
                        self.datastore.create_dset(
                            'hmaps/' + statname, F32, (N, P * I))
                        self.datastore.set_attrs(
                            'hmaps/' + statname, nbytes=N * P * I * 4)
                        hmap = calc.make_hmap(pmap, oq.imtls, oq.poes)
                        ds = self.datastore['hmaps/' + statname]
                        for sid in hmap:
                            ds[sid] = hmap[sid].array[:, 0]

        if self.datastore.parent:
            self.datastore.parent.open('r')
        if 'gmf_data' in self.datastore:
            self.save_gmf_bytes()
        if oq.compare_with_classical:  # compute classical curves
            export_dir = os.path.join(oq.export_dir, 'cl')
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            oq.export_dir = export_dir
            # one could also set oq.number_of_logic_tree_samples = 0
            self.cl = ClassicalCalculator(oq)
            # TODO: perhaps it is possible to avoid reprocessing the source
            # model, however usually this is quite fast and do not dominate
            # the computation
            self.cl.run(close=False)
            cl_mean_curves = get_mean_curves(self.cl.datastore)
            eb_mean_curves = get_mean_curves(self.datastore)
            rdiff, index = util.max_rel_diff_index(
                cl_mean_curves, eb_mean_curves)
            logging.warn('Relative difference with the classical '
                         'mean curves: %d%% at site index %d',
                         rdiff * 100, index)
