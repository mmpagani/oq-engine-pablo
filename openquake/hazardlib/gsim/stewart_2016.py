# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (C) 2012-2021 GEM Foundation
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

"""
Module exports :class:`StewartEtAl2016`,
               :class:`StewartEtAl2016RegCHN`,
               :class:`StewartEtAl2016RegJPN`,
               :class:`StewartEtAl2016NoSOF`,
               :class:`StewartEtAl2016RegCHNNoSOF`,
               :class:`StewartEtAl2016RegJPNNoSOF`,
"""

import numpy as np

from openquake.hazardlib.gsim.base import CoeffsTable, gsim_aliases
from openquake.hazardlib.gsim.boore_2014 import BooreEtAl2014
from openquake.hazardlib import const
from openquake.hazardlib.imt import PGA, PGV, SA


class StewartEtAl2016(BooreEtAl2014):
    """
    Implements the SBSA15 GMPE by Stewart et al. (2016) for vertical-component
    ground motions from the PEER NGA-West2 Project.

    This model follows the same functional form as in BSSA14 by Boore et
    al. (2014) with minor modifications.

    Note that this is a more updated version than the GMPE described in the
    original PEER Report 2013/24.

    **Reference:**

    Stewart, J., Boore, D., Seyhan, E., & Atkinson, G. (2016). NGA-West2
    Equations for Predicting Vertical-Component PGA, PGV, and 5%-Damped PSA
    from Shallow Crustal Earthquakes. *Earthquake Spectra*, *32*(2), 1005-1031.
    """
    region = "CAL"

    #: Supported tectonic region type is active shallow crust; see title.
    DEFINED_FOR_TECTONIC_REGION_TYPE = const.TRT.ACTIVE_SHALLOW_CRUST

    #: Supported intensity measure types are spectral acceleration,
    #: peak ground velocity and peak ground acceleration; see title.
    DEFINED_FOR_INTENSITY_MEASURE_TYPES = {PGA, PGV, SA}

    #: Supported intensity measure component is the
    #: :attr:`~openquake.hazardlib.const.IMC.Vertical` direction component;
    #: see title.
    DEFINED_FOR_INTENSITY_MEASURE_COMPONENT = const.IMC.VERTICAL

    #: Supported standard deviation types are inter-event, intra-event
    #: and total; see the section for "Aleatory-Uncertainty Function".
    DEFINED_FOR_STANDARD_DEVIATION_TYPES = {
        const.StdDev.TOTAL, const.StdDev.INTER_EVENT, const.StdDev.INTRA_EVENT}

    #: Required site parameter is Vs30
    REQUIRES_SITES_PARAMETERS = {'vs30'}

    #: Required rupture parameters are magnitude and rake (style-of-faulting).
    REQUIRES_RUPTURE_PARAMETERS = {'mag', 'rake'}

    #: Required distance measure is Rjb
    REQUIRES_DISTANCES = {'rjb'}

    REQUIRES_ATTRIBUTES = {'region', 'sof'}

    kind = "stewart"

    def __init__(self, region='CAL', sof=True, **kwargs):
        super().__init__(**kwargs)
        self.region = region
        self.sof = sof

    def get_mean_and_stddevs(self, sites, rup, dists, imt, stddev_types):
        """
        See :meth:`superclass method
        <.base.GroundShakingIntensityModel.get_mean_and_stddevs>`
        for spec of input and result values.
        """
        # extracting dictionary of coefficients specific to required
        # intensity measure type.
        C = self.COEFFS[imt]
        C_PGA = self.COEFFS[PGA()]
        # Retrieve PGAr case
        pga_rock = self._get_pga_on_rock(C_PGA, rup, dists)
        # SBSA15 Functional Form, Equation 1 (in natural log units)
        mean = (self._get_magnitude_scaling_term(C, rup) +
                self._get_path_scaling(C, dists.rjb, rup.mag) +
                self._get_site_scaling(C, pga_rock, sites, None, dists.rjb))
        # SBSA15 Std Dev Model, Equations 9 to 11 (in natural log units)
        stddevs = self._get_stddevs(C, rup, sites, stddev_types)
        return mean, stddevs

    def _get_pga_on_rock(self, C, rup, dists):
        """
        Returns the median PGA on rock (in g units), PGAr, which is a sum of
        the magnitude and distance scaling. Precisely, it is obtained by
        evaluating Equation 1 for the given magnitude, fault mechanism, and Rjb
        with Vs30=760 m∕s.
        """
        return np.exp(self._get_magnitude_scaling_term(C, rup) +
                      self._get_path_scaling(C, dists.rjb, rup.mag))

    def _get_magnitude_scaling_term(self, C, rup):
        """
        Returns the magnitude scaling term component, defined in Equation 2
        """
        return BooreEtAl2014._get_magnitude_scaling_term(self, C, rup)

    def _get_style_of_faulting_term(self, C, rup):
        """
        Returns the style-of-faulting term component, defined in Equation 2
        """
        if not self.sof:
            return C["e0"]  # Unspecified style-of-faulting
        return super()._get_style_of_faulting_term(C, rup)

    def _get_path_scaling(self, C, rjb, mag):
        """
        Returns the path scaling term defined in Equation 3
        """
        # Calculate R in Equation 4
        rval = np.sqrt((rjb ** 2.0) + (C["h"] ** 2.0))
        if self.region == "CAL":
            delta_c3 = 0
        elif self.region == "CHN":
            delta_c3 = C['Dc3CH']
        elif self.region == "JPN":
            delta_c3 = C['Dc3JP']
        else:
            raise ValueError("region=%s" % self.region)

        # Calculate geometric spreading component of path scaling term
        fp_geom = ((C["c1"] + C["c2"] * (mag - self.CONSTS["Mref"])) *
                   np.log(rval / self.CONSTS["Rref"]))
        # Calculate anelastic attenuation component of path scaling term, with
        # delta c3 accounting for regional effects
        fp_atten = (C["c3"] + delta_c3) * (rval - self.CONSTS["Rref"])
        return fp_geom + fp_atten

    def _get_basin_depth_term(self, C, sites, period):
        """
        Unlike in BSSA14, basin depth effects are not accounted for in this
        model.
        """
        return 0.

    def _get_stddevs(self, C, rup, sites, stddev_types):
        """
        Returns the aleatory uncertainty terms described in Equations 9 to 11
        """
        stddevs = []
        num_sites = len(sites.vs30)
        tau = self._get_inter_event_tau(C, rup.mag)
        phi = self._get_intra_event_phi(C, rup.mag)
        for stddev_type in stddev_types:
            assert stddev_type in self.DEFINED_FOR_STANDARD_DEVIATION_TYPES
            if stddev_type == const.StdDev.TOTAL:
                stddevs.append(np.sqrt((tau ** 2.0) + (phi ** 2.0)) +
                               np.zeros(num_sites))
            elif stddev_type == const.StdDev.INTRA_EVENT:
                stddevs.append(phi + np.zeros(num_sites))
            elif stddev_type == const.StdDev.INTER_EVENT:
                stddevs.append(tau + np.zeros(num_sites))
        # return std dev values for each stddev type in site collection
        return stddevs

    def _get_inter_event_tau(self, C, mag):
        """
        Returns the inter-event standard deviation (tau), which is dependent
        on magnitude
        """
        if mag <= 4.5:
            tau = C["tau1"]
        elif mag >= 5.5:
            tau = C["tau2"]
        else:
            tau = C["tau1"] + (C["tau2"] - C["tau1"]) * (mag - 4.5)
        return tau

    def _get_intra_event_phi(self, C, mag):
        """
        Returns the intra-event standard deviation (phi)

        In SBSA15, the intra-event standard deviation only depends on magnitude
        """
        if mag <= 4.5:
            phi = C["phi1"]
        elif mag >= 5.5:
            phi = C["phi2"]
        else:
            phi = (C["phi1"] + (C["phi2"] - C["phi1"]) * (mag - 4.5))
        return phi

    #: Equation constants that are IMT-independent
    CONSTS = {
        "Mref": 4.5,
        "Rref": 1.0,
        "Vref": 760.0,
        "f1": 0.0,
        "f3": 0.1}

    #: Table of period-dependent regression coefficients obtained from the
    #: supplementary material in EQS paper
    COEFFS = CoeffsTable(sa_damping=5, table="""\
    IMT      e0           e1           e2           e3           e4          e5           e6           Mh          c1           c2          c3           Dc3CH       Dc3JP        h           c            Vc             f4           f5           tau1       tau2       phi1       phi2
    pgv      4.267000     4.292000     4.179000     4.255000     0.992500    -0.111400    0.247000     6.200000    -1.254000    0.171500    -0.003400    0.003360    0.000000     6.900000    -0.518000    1300.000000    -0.030000    -0.008440    0.38571    0.34879    0.58241    0.59672
    pga      0.183600     0.233700     0.015620     0.153800     1.247000    0.000000     0.022570     5.500000    -1.175000    0.157700    -0.009222    0.004750    0.000000     5.100000    -0.329000    1500.000000    -0.050000    -0.007010    0.47631    0.37634    0.71175    0.53387
    0.010    0.204500     0.255300     0.035100     0.174100     1.242000    0.000000     0.022200     5.500000    -1.176000    0.157300    -0.009222    0.004980    0.000000     5.100000    -0.329000    1500.000000    -0.050000    -0.007010    0.48088    0.38052    0.71450    0.53338
    0.020    0.393700     0.446800     0.229500     0.356800     1.243000    0.000000     0.010380     5.500000    -1.212000    0.159800    -0.009039    0.005207    0.000000     5.060000    -0.318000    1500.100000    -0.050100    -0.007279    0.48986    0.38818    0.71842    0.53832
    0.022    0.444900     0.499000     0.280500     0.406200     1.240000    0.000000     0.008442     5.500000    -1.221000    0.160300    -0.009038    0.005251    0.000000     5.030000    -0.311000    1501.000000    -0.050100    -0.007311    0.50166    0.39681    0.72473    0.54263
    0.025    0.531300     0.587700     0.366500     0.488100     1.232000    0.000000     0.006672     5.500000    -1.233000    0.160800    -0.009071    0.005316    0.000000     4.990000    -0.301000    1501.000000    -0.050100    -0.007336    0.51211    0.40462    0.73090    0.54692
    0.029    0.646400     0.706100     0.485700     0.595400     1.220000    0.000000     0.007363     5.500000    -1.243000    0.161100    -0.009209    0.005400    0.000000     4.990000    -0.298000    1502.000000    -0.049800    -0.007310    0.52178    0.41180    0.73706    0.55165
    0.030    0.671200     0.731500     0.512000     0.618200     1.217000    0.000000     0.008618     5.500000    -1.245000    0.160800    -0.009260    0.005420    0.000000     4.990000    -0.297000    1502.000000    -0.049700    -0.007293    0.53152    0.41915    0.74357    0.55669
    0.032    0.715800     0.777400     0.560300     0.658900     1.215000    0.000000     0.012710     5.500000    -1.246000    0.160100    -0.009389    0.005460    0.000000     5.010000    -0.298000    1502.000000    -0.049700    -0.007246    0.54117    0.42658    0.74967    0.56253
    0.035    0.772800     0.835900     0.622900     0.710400     1.212000    0.000000     0.020860     5.500000    -1.244000    0.158400    -0.009629    0.005518    0.000000     5.030000    -0.300000    1503.000000    -0.050400    -0.007148    0.54987    0.43291    0.75553    0.56688
    0.036    0.788800     0.852500     0.641100     0.724800     1.212000    0.000000     0.023990     5.500000    -1.243000    0.157600    -0.009720    0.005536    0.000000     5.030000    -0.304000    1503.000000    -0.050800    -0.007111    0.55808    0.43902    0.76129    0.57120
    0.040    0.836700     0.902100     0.694500     0.767200     1.215000    0.000000     0.036920     5.500000    -1.232000    0.154400    -0.010120    0.005603    0.000000     5.030000    -0.319000    1502.900000    -0.053500    -0.006937    0.56537    0.44490    0.76670    0.57554
    0.042    0.853100     0.918900     0.711200     0.782200     1.219000    0.000000     0.044660     5.500000    -1.226000    0.152300    -0.010340    0.005633    0.000000     5.010000    -0.324000    1502.000000    -0.055300    -0.006844    0.57111    0.45020    0.77122    0.57948
    0.044    0.865100     0.931600     0.722300     0.793600     1.223000    0.000000     0.052660     5.500000    -1.218000    0.150100    -0.010550    0.005658    0.000000     4.990000    -0.331000    1502.000000    -0.057300    -0.006749    0.57640    0.45620    0.77588    0.58323
    0.045    0.869400     0.936200     0.725500     0.797600     1.225000    0.000000     0.057050     5.500000    -1.214000    0.148800    -0.010660    0.005670    0.000000     4.980000    -0.339000    1502.000000    -0.058400    -0.006702    0.58036    0.46245    0.78032    0.58680
    0.046    0.873400     0.940600     0.728400     0.801400     1.228000    0.000000     0.061550     5.500000    -1.210000    0.147500    -0.010770    0.005680    0.000000     4.970000    -0.349000    1502.000000    -0.059400    -0.006655    0.58236    0.46826    0.78388    0.58984
    0.048    0.880700     0.948800     0.732800     0.808400     1.233000    0.000000     0.071300     5.500000    -1.201000    0.144800    -0.010970    0.005697    0.000000     4.960000    -0.358000    1501.900000    -0.061600    -0.006564    0.58365    0.47388    0.78704    0.59264
    0.050    0.886400     0.955100     0.735400     0.814000     1.240000    0.000000     0.081060     5.500000    -1.193000    0.142000    -0.011160    0.005710    0.000000     4.940000    -0.365000    1501.100000    -0.063600    -0.006476    0.58317    0.47865    0.78898    0.59452
    0.055    0.892200     0.962400     0.731500     0.820800     1.257000    0.000000     0.103900     5.500000    -1.170000    0.134800    -0.011570    0.005720    0.000000     4.900000    -0.372000    1500.000000    -0.068200    -0.006275    0.58127    0.48279    0.78996    0.59600
    0.060    0.885500     0.956800     0.710200     0.817600     1.276000    0.000000     0.123200     5.500000    -1.147000    0.128500    -0.011870    0.005702    0.000000     4.900000    -0.380000    1499.100000    -0.071500    -0.006105    0.57818    0.48610    0.79012    0.59731
    0.065    0.875000     0.946800     0.683900     0.812700     1.297000    0.000000     0.142000     5.500000    -1.126000    0.122400    -0.012070    0.005662    0.000000     4.900000    -0.386000    1497.400000    -0.073400    -0.005968    0.57413    0.48862    0.78988    0.59879
    0.067    0.871600     0.943300     0.674600     0.811900     1.306000    0.000000     0.148800     5.500000    -1.118000    0.120000    -0.012130    0.005640    0.000000     4.900000    -0.392000    1496.700000    -0.073900    -0.005922    0.56897    0.49021    0.78934    0.60035
    0.070    0.867100     0.938400     0.661500     0.811500     1.320000    0.000000     0.157900     5.500000    -1.107000    0.116600    -0.012180    0.005604    0.000000     4.900000    -0.397000    1495.500000    -0.074500    -0.005860    0.56264    0.49063    0.78845    0.60176
    0.075    0.859800     0.930100     0.642100     0.810800     1.345000    0.000000     0.169700     5.500000    -1.091000    0.111500    -0.012220    0.005534    0.000000     4.900000    -0.400000    1493.200000    -0.074900    -0.005778    0.55545    0.49009    0.78729    0.60305
    0.080    0.853000     0.922100     0.627200     0.809800     1.367000    0.000000     0.175700     5.500000    -1.076000    0.107700    -0.012180    0.005457    0.000000     4.880000    -0.403000    1490.700000    -0.075100    -0.005719    0.54698    0.48743    0.78560    0.60433
    0.085    0.849000     0.917000     0.615500     0.810800     1.386000    0.000000     0.174000     5.510000    -1.064000    0.105200    -0.012080    0.005378    0.000000     4.850000    -0.404000    1488.100000    -0.075000    -0.005678    0.53771    0.48252    0.78355    0.60534
    0.090    0.847300     0.914600     0.607200     0.813300     1.402000    0.000000     0.167400     5.520000    -1.054000    0.103800    -0.011965    0.005302    0.000000     4.830000    -0.404000    1485.600000    -0.074700    -0.005652    0.52787    0.47587    0.78144    0.60605
    0.095    0.847400     0.913800     0.602700     0.816800     1.414000    0.000000     0.157400     5.530000    -1.047000    0.102900    -0.011835    0.005234    -0.000100    4.810000    -0.404000    1482.300000    -0.074200    -0.005639    0.51796    0.46886    0.77937    0.60665
    0.100    0.848700     0.914100     0.601100     0.821200     1.425000    0.000000     0.144400     5.540000    -1.040000    0.102300    -0.011690    0.005180    -0.000250    4.800000    -0.404000    1480.000000    -0.073600    -0.005636    0.50759    0.46128    0.77723    0.60694
    0.110    0.849800     0.912900     0.599600     0.828000     1.440000    -0.000062    0.109600     5.570000    -1.028000    0.102400    -0.011370    0.005121    -0.000450    4.790000    -0.403000    1473.700000    -0.071700    -0.005653    0.49674    0.45327    0.77496    0.60670
    0.120    0.840300     0.900700     0.592500     0.822400     1.438000    -0.003053    0.071260     5.620000    -1.017000    0.104200    -0.011055    0.005117    -0.000650    4.760000    -0.402000    1466.200000    -0.069200    -0.005691    0.48550    0.44500    0.77239    0.60589
    0.130    0.823200     0.880400     0.582700     0.808800     1.419000    -0.010370    0.031430     5.660000    -1.010000    0.107000    -0.010725    0.005148    -0.000850    4.770000    -0.401000    1458.500000    -0.066400    -0.005742    0.47414    0.43678    0.76941    0.60455
    0.133    0.816200     0.872300     0.578300     0.803100     1.412000    -0.013000    0.020290     5.670000    -1.008000    0.107900    -0.010620    0.005162    -0.000900    4.770000    -0.400000    1456.000000    -0.065500    -0.005758    0.46295    0.42907    0.76592    0.60277
    0.140    0.794800     0.847800     0.563400     0.785100     1.391000    -0.020220    -0.002279    5.700000    -1.003000    0.109900    -0.010400    0.005196    -0.001100    4.780000    -0.400000    1450.200000    -0.063500    -0.005797    0.45200    0.42226    0.76189    0.60064
    0.150    0.755400     0.803700     0.533500     0.750900     1.354000    -0.032830    -0.027980    5.740000    -0.996000    0.112600    -0.010125    0.005240    -0.001320    4.780000    -0.400000    1441.200000    -0.060700    -0.005855    0.44110    0.41616    0.75743    0.59834
    0.160    0.710900     0.754800     0.499200     0.710700     1.311000    -0.047320    -0.047110    5.780000    -0.990100    0.115200    -0.009805    0.005266    -0.001520    4.780000    -0.400000    1431.600000    -0.058100    -0.005915    0.43033    0.41044    0.75224    0.59616
    0.170    0.662400     0.701900     0.463100     0.665800     1.263000    -0.063640    -0.060970    5.820000    -0.985500    0.117500    -0.009505    0.005271    -0.001680    4.760000    -0.401000    1422.300000    -0.055700    -0.005976    0.41998    0.40507    0.74608    0.59390
    0.180    0.612500     0.647800     0.426300     0.618900     1.211000    -0.081030    -0.070710    5.850000    -0.981800    0.119900    -0.009220    0.005257    -0.001830    4.760000    -0.402000    1413.700000    -0.053400    -0.006036    0.41042    0.40114    0.73979    0.59190
    0.190    0.563000     0.594300     0.389400     0.571700     1.159000    -0.098180    -0.077370    5.890000    -0.979000    0.122100    -0.008955    0.005227    -0.001950    4.770000    -0.403000    1405.400000    -0.051200    -0.006096    0.40067    0.39772    0.73340    0.59015
    0.200    0.516500     0.544300     0.354400     0.527400     1.110000    -0.113900    -0.081940    5.920000    -0.977200    0.124100    -0.008710    0.005181    -0.002050    4.790000    -0.403000    1396.500000    -0.049200    -0.006156    0.39107    0.39407    0.72692    0.58894
    0.220    0.431200     0.452700     0.284100     0.448200     1.025000    -0.142300    -0.086350    5.970000    -0.973600    0.126700    -0.008254    0.005050    -0.002200    4.780000    -0.402000    1378.900000    -0.046100    -0.006273    0.38255    0.39038    0.72077    0.58828
    0.240    0.353700     0.370300     0.215600     0.376600     0.954600    -0.166800    -0.086490    6.030000    -0.970300    0.128700    -0.007846    0.004878    -0.002300    4.800000    -0.401000    1360.900000    -0.043500    -0.006388    0.37488    0.38670    0.71489    0.58799
    0.250    0.319200     0.333600     0.184400     0.345300     0.925300    -0.177600    -0.085780    6.050000    -0.969000    0.129200    -0.007662    0.004781    -0.002330    4.810000    -0.400000    1352.900000    -0.042400    -0.006444    0.36761    0.38296    0.70866    0.58803
    0.260    0.286500     0.298800     0.153800     0.315800     0.899800    -0.187300    -0.085650    6.070000    -0.968200    0.129800    -0.007482    0.004678    -0.002350    4.830000    -0.398000    1344.500000    -0.041600    -0.006499    0.36064    0.37935    0.70194    0.58831
    0.280    0.227200     0.236400     0.095150     0.262000     0.861000    -0.202700    -0.086060    6.110000    -0.967200    0.130900    -0.007150    0.004464    -0.002370    4.880000    -0.396000    1329.100000    -0.040200    -0.006605    0.35420    0.37544    0.69533    0.58880
    0.290    0.199800     0.207900     0.067250     0.236900     0.846600    -0.209000    -0.085510    6.120000    -0.966800    0.131300    -0.006993    0.004356    -0.002370    4.910000    -0.393000    1320.800000    -0.039700    -0.006655    0.34827    0.37113    0.68878    0.58938
    0.300    0.173100     0.180600     0.039650     0.212100     0.835500    -0.214700    -0.084100    6.140000    -0.966500    0.131600    -0.006843    0.004250    -0.002370    4.940000    -0.390000    1313.400000    -0.039000    -0.006704    0.34336    0.36726    0.68223    0.58959
    0.320    0.124300     0.130700     -0.011770    0.166500     0.820500    -0.224300    -0.083610    6.160000    -0.966300    0.132000    -0.006556    0.004046    -0.002370    5.000000    -0.388000    1298.700000    -0.038000    -0.006799    0.33929    0.36432    0.67601    0.58966
    0.340    0.075900     0.081910     -0.062540    0.119700     0.810900    -0.232200    -0.083050    6.180000    -0.966700    0.132800    -0.006287    0.003855    -0.002370    5.050000    -0.385000    1286.300000    -0.037100    -0.006887    0.33577    0.36162    0.66960    0.58953
    0.350    0.051840     0.057870     -0.087720    0.096010     0.807700    -0.235600    -0.082730    6.180000    -0.967200    0.133200    -0.006157    0.003764    -0.002370    5.070000    -0.382000    1280.000000    -0.036700    -0.006929    0.33291    0.35912    0.66299    0.58928
    0.360    0.028530     0.034660     -0.112000    0.072870     0.805600    -0.238800    -0.082130    6.190000    -0.968000    0.133700    -0.006030    0.003676    -0.002360    5.100000    -0.380000    1273.800000    -0.036200    -0.006970    0.33102    0.35746    0.65662    0.58886
    0.380    -0.016120    -0.009451    -0.158800    0.028040     0.804900    -0.244000    -0.080620    6.190000    -0.970100    0.134400    -0.005789    0.003509    -0.002360    5.150000    -0.380000    1262.100000    -0.035400    -0.007047    0.32955    0.35635    0.65034    0.58843
    0.400    -0.057690    -0.050400    -0.202200    -0.013920    0.809400    -0.247800    -0.078070    6.200000    -0.972800    0.135000    -0.005559    0.003354    -0.002350    5.190000    -0.380000    1252.100000    -0.034800    -0.007122    0.32873    0.35508    0.64402    0.58813
    0.420    -0.097200    -0.089280    -0.242400    -0.054410    0.818700    -0.250100    -0.075060    6.200000    -0.975400    0.135600    -0.005344    0.003209    -0.002340    5.230000    -0.381000    1242.500000    -0.034300    -0.007192    0.32888    0.35348    0.63827    0.58788
    0.440    -0.135400    -0.127000    -0.279800    -0.093890    0.829600    -0.252000    -0.071020    6.200000    -0.978000    0.136100    -0.005138    0.003075    -0.002320    5.270000    -0.384000    1233.600000    -0.033900    -0.007259    0.33050    0.35127    0.63273    0.58779
    0.450    -0.154300    -0.145800    -0.297400    -0.113500    0.835100    -0.252800    -0.068920    6.200000    -0.979200    0.136500    -0.005042    0.003013    -0.002320    5.280000    -0.388000    1229.700000    -0.033700    -0.007292    0.33310    0.34994    0.62713    0.58778
    0.460    -0.172800    -0.164200    -0.314600    -0.132700    0.840600    -0.253600    -0.067030    6.200000    -0.980500    0.136800    -0.004947    0.002952    -0.002310    5.300000    -0.393000    1225.900000    -0.033500    -0.007324    0.33668    0.34969    0.62163    0.58804
    0.480    -0.208500    -0.199800    -0.347000    -0.169900    0.852000    -0.254900    -0.064270    6.200000    -0.983400    0.137700    -0.004765    0.002839    -0.002290    5.330000    -0.400000    1218.600000    -0.033000    -0.007387    0.34092    0.34988    0.61666    0.58865
    0.500    -0.240400    -0.231800    -0.375500    -0.202700    0.865300    -0.255500    -0.062140    6.200000    -0.986700    0.138400    -0.004596    0.002735    -0.002280    5.350000    -0.406000    1212.400000    -0.032500    -0.007449    0.34660    0.35009    0.61140    0.58959
    0.550    -0.313700    -0.305600    -0.441500    -0.278000    0.903000    -0.255800    -0.050230    6.200000    -0.994700    0.139000    -0.004206    0.002515    -0.002230    5.400000    -0.413000    1195.900000    -0.031000    -0.007598    0.35369    0.34934    0.60584    0.59069
    0.600    -0.372800    -0.365200    -0.496900    -0.337800    0.947500    -0.252900    -0.036400    6.200000    -1.005000    0.138900    -0.003867    0.002347    -0.002170    5.490000    -0.421000    1181.600000    -0.029600    -0.007739    0.36128    0.34783    0.60059    0.59190
    0.650    -0.419700    -0.412600    -0.538700    -0.385800    0.995800    -0.247700    -0.025210    6.200000    -1.015000    0.138800    -0.003578    0.002225    -0.002110    5.620000    -0.431000    1170.100000    -0.028500    -0.007870    0.36905    0.34636    0.59562    0.59324
    0.667    -0.433900    -0.426900    -0.551400    -0.400400    1.012000    -0.245800    -0.020750    6.200000    -1.018000    0.138700    -0.003490    0.002193    -0.002080    5.670000    -0.441000    1166.600000    -0.028000    -0.007912    0.37718    0.34554    0.59069    0.59468
    0.700    -0.459000    -0.452400    -0.574600    -0.425900    1.043000    -0.242100    -0.011470    6.200000    -1.026000    0.138400    -0.003326    0.002143    -0.002040    5.780000    -0.452000    1159.500000    -0.027200    -0.007989    0.38573    0.34616    0.58583    0.59622
    0.750    -0.491200    -0.485100    -0.605300    -0.457500    1.090000    -0.236200    0.002752     6.200000    -1.037000    0.137700    -0.003110    0.002096    -0.001960    5.960000    -0.464000    1149.700000    -0.026000    -0.008094    0.39468    0.34832    0.58105    0.59794
    0.800    -0.517100    -0.511700    -0.630800    -0.482000    1.137000    -0.230100    0.019870     6.200000    -1.048000    0.136500    -0.002923    0.002077    -0.001890    6.160000    -0.475000    1140.100000    -0.024900    -0.008184    0.40371    0.35201    0.57688    0.60008
    0.850    -0.540700    -0.535700    -0.654500    -0.504600    1.183000    -0.224000    0.039440     6.200000    -1.060000    0.135100    -0.002758    0.002081    -0.001810    6.370000    -0.486000    1132.200000    -0.023900    -0.008258    0.41267    0.35536    0.57320    0.60269
    0.900    -0.561400    -0.557000    -0.675200    -0.524500    1.228000    -0.217600    0.060230     6.200000    -1.071000    0.133500    -0.002616    0.002102    -0.001730    6.560000    -0.497000    1124.700000    -0.023100    -0.008315    0.42177    0.35813    0.56959    0.60562
    0.950    -0.579300    -0.575400    -0.692600    -0.541600    1.274000    -0.211100    0.082750     6.200000    -1.080000    0.131600    -0.002485    0.002133    -0.001650    6.750000    -0.508000    1118.600000    -0.022200    -0.008356    0.43138    0.36128    0.56586    0.60904
    1.000    -0.595300    -0.591800    -0.708200    -0.557100    1.320000    -0.204600    0.106900     6.200000    -1.089000    0.129200    -0.002360    0.002170    -0.001580    6.940000    -0.518000    1113.000000    -0.021500    -0.008378    0.44039    0.36527    0.56270    0.61298
    1.100    -0.623200    -0.619800    -0.737600    -0.583900    1.411000    -0.191900    0.154600     6.200000    -1.104000    0.123600    -0.002185    0.002243    -0.001430    7.330000    -0.528000    1103.700000    -0.020200    -0.008363    0.44865    0.37022    0.56000    0.61729
    1.200    -0.648800    -0.645800    -0.763500    -0.608600    1.497000    -0.180300    0.199400     6.200000    -1.116000    0.117300    -0.002030    0.002314    -0.001300    7.700000    -0.538000    1095.200000    -0.019100    -0.008264    0.45699    0.37512    0.55702    0.62157
    1.300    -0.678800    -0.675700    -0.792300    -0.639400    1.574000    -0.170700    0.253000     6.200000    -1.126000    0.110200    -0.001875    0.002382    -0.001180    8.070000    -0.547000    1086.500000    -0.017800    -0.008062    0.46569    0.37939    0.55374    0.62567
    1.400    -0.713000    -0.710000    -0.822300    -0.675100    1.641000    -0.163300    0.304900     6.200000    -1.136000    0.103600    -0.001745    0.002446    -0.001070    8.400000    -0.557000    1077.200000    -0.016400    -0.007762    0.47450    0.38315    0.55065    0.62969
    1.500    -0.750400    -0.747200    -0.853400    -0.715200    1.698000    -0.157600    0.353800     6.200000    -1.144000    0.097710    -0.001620    0.002506    -0.000974    8.720000    -0.567000    1067.400000    -0.015200    -0.007375    0.48287    0.38675    0.54793    0.63347
    1.600    -0.788900    -0.786400    -0.883900    -0.755800    1.752000    -0.151300    0.398400     6.200000    -1.152000    0.092370    -0.001520    0.002563    -0.000886    8.990000    -0.578000    1056.400000    -0.014100    -0.006918    0.49017    0.39115    0.54490    0.63652
    1.700    -0.828400    -0.827000    -0.909800    -0.798500    1.801000    -0.145000    0.441500     6.200000    -1.160000    0.087630    -0.001415    0.002617    -0.000807    9.170000    -0.590000    1045.300000    -0.012900    -0.006419    0.49619    0.39502    0.54147    0.63887
    1.800    -0.868900    -0.868500    -0.934400    -0.843500    1.847000    -0.138800    0.484500     6.200000    -1.168000    0.083280    -0.001340    0.002666    -0.000737    9.310000    -0.602000    1034.900000    -0.011800    -0.005903    0.50150    0.39819    0.53791    0.64067
    1.900    -0.910000    -0.909900    -0.960600    -0.890100    1.893000    -0.132100    0.526300     6.200000    -1.173000    0.079130    -0.001265    0.002711    -0.000675    9.460000    -0.613000    1024.600000    -0.010900    -0.005387    0.50599    0.40069    0.53450    0.64182
    2.000    -0.953000    -0.954200    -0.988900    -0.936300    1.934000    -0.126500    0.566300     6.200000    -1.177000    0.074950    -0.001190    0.002751    -0.000621    9.560000    -0.625000    1014.400000    -0.010200    -0.004886    0.50993    0.40204    0.53133    0.64194
    2.200    -1.044000    -1.050000    -1.041000    -1.032000    2.017000    -0.112400    0.635900     6.200000    -1.181000    0.068200    -0.001088    0.002818    -0.000534    9.600000    -0.638000    992.760000     -0.008960    -0.003985    0.51349    0.40210    0.52829    0.64107
    2.400    -1.138000    -1.154000    -1.094000    -1.126000    2.097000    -0.095690    0.701100     6.200000    -1.182000    0.062710    -0.000991    0.002865    -0.000470    9.530000    -0.645000    973.490000     -0.007900    -0.003255    0.51650    0.40148    0.52515    0.63976
    2.500    -1.186000    -1.206000    -1.125000    -1.173000    2.131000    -0.088240    0.732500     6.200000    -1.182000    0.060530    -0.000948    0.002880    -0.000446    9.490000    -0.648000    964.540000     -0.007420    -0.002959    0.51870    0.40085    0.52186    0.63872
    2.600    -1.238000    -1.261000    -1.161000    -1.225000    2.161000    -0.081800    0.763500     6.200000    -1.181000    0.058880    -0.000900    0.002890    -0.000426    9.460000    -0.651000    956.160000     -0.006970    -0.002707    0.52015    0.40044    0.51853    0.63798
    2.800    -1.349000    -1.377000    -1.241000    -1.336000    2.217000    -0.068820    0.824200     6.200000    -1.176000    0.055730    -0.000810    0.002892    -0.000397    9.450000    -0.652000    939.010000     -0.006150    -0.002307    0.52097    0.39980    0.51491    0.63739
    3.000    -1.463000    -1.496000    -1.330000    -1.453000    2.268000    -0.056800    0.883600     6.200000    -1.168000    0.052610    -0.000704    0.002870    -0.000350    9.490000    -0.645000    921.230000     -0.005430    -0.002025    0.52179    0.39886    0.51070    0.63690
    3.200    -1.581000    -1.619000    -1.425000    -1.569000    2.303000    -0.048700    0.938200     6.200000    -1.160000    0.050690    -0.000639    0.002822    -0.000200    9.510000    -0.641000    904.140000     -0.004790    -0.001836    0.52305    0.39689    0.50642    0.63678
    3.400    -1.689000    -1.731000    -1.509000    -1.677000    2.333000    -0.039880    0.981900     6.200000    -1.156000    0.050610    -0.000577    0.002752    -0.000120    9.480000    -0.630000    888.700000     -0.004230    -0.001710    0.52408    0.39438    0.50215    0.63691
    3.500    -1.740000    -1.784000    -1.553000    -1.730000    2.347000    -0.035940    1.001000     6.200000    -1.154000    0.050710    -0.000547    0.002710    -0.000100    9.470000    -0.628000    881.420000     -0.003970    -0.001662    0.52485    0.39179    0.49792    0.63691
    3.600    -1.792000    -1.836000    -1.601000    -1.782000    2.361000    -0.032380    1.020000     6.200000    -1.151000    0.050570    -0.000519    0.002663    -0.000095    9.480000    -0.623000    874.260000     -0.003730    -0.001625    0.52561    0.38959    0.49358    0.63656
    3.800    -1.894000    -1.937000    -1.700000    -1.890000    2.385000    -0.026020    1.055000     6.200000    -1.144000    0.050080    -0.000464    0.002559    0.000000     9.490000    -0.611000    860.430000     -0.003300    -0.001568    0.52656    0.38729    0.48900    0.63664
    4.000    -1.999000    -2.039000    -1.806000    -1.999000    2.413000    -0.020680    1.088000     6.200000    -1.133000    0.048750    -0.000412    0.002443    0.000000     9.510000    -0.600000    847.560000     -0.002930    -0.001530    0.52701    0.38482    0.48369    0.63725
    4.200    -2.103000    -2.141000    -1.910000    -2.106000    2.438000    -0.015490    1.116000     6.200000    -1.121000    0.047640    -0.000362    0.002318    0.000000     9.520000    -0.590000    835.890000     -0.002570    -0.001504    0.52914    0.38235    0.47779    0.63808
    4.400    -2.203000    -2.241000    -2.011000    -2.208000    2.462000    -0.011090    1.142000     6.200000    -1.110000    0.046810    -0.000315    0.002189    0.000000     9.540000    -0.578000    825.460000     -0.002240    -0.001485    0.53211    0.38034    0.47172    0.63903
    4.600    -2.305000    -2.344000    -2.109000    -2.309000    2.476000    -0.008411    1.164000     6.200000    -1.101000    0.046890    -0.000270    0.002059    0.000000     9.540000    -0.563000    816.480000     -0.001920    -0.001470    0.53349    0.37980    0.46516    0.63997
    4.800    -2.407000    -2.450000    -2.206000    -2.408000    2.483000    -0.007098    1.181000     6.200000    -1.092000    0.048030    -0.000227    0.001931    0.000000     9.530000    -0.544000    809.050000     -0.001610    -0.001457    0.53685    0.38183    0.45784    0.64043
    5.000    -2.512000    -2.558000    -2.306000    -2.506000    2.488000    -0.005876    1.192000     6.200000    -1.085000    0.050140    -0.000185    0.001810    0.000000     9.500000    -0.522000    802.670000     -0.001350    -0.001446    0.53961    0.38549    0.44984    0.63998
    5.500    -2.776000    -2.831000    -2.564000    -2.753000    2.496000    -0.001251    1.204000     6.200000    -1.065000    0.057980    -0.000088    0.001546    0.000000     9.360000    -0.476000    790.210000     -0.000823    -0.001417    0.53757    0.38679    0.44248    0.63865
    6.000    -3.053000    -3.120000    -2.836000    -3.010000    2.492000    -0.000063    1.206000     6.200000    -1.043000    0.067320    0.000000     0.001337    0.000000     9.100000    -0.437000    782.060000     -0.000456    -0.001396    0.53492    0.38948    0.43556    0.63641
    6.500    -3.325000    -3.406000    -3.103000    -3.256000    2.467000    0.000000     1.194000     6.200000    -1.030000    0.080820    0.000000     0.001176    0.000000     8.690000    -0.400000    776.360000     -0.000215    -0.001383    0.53281    0.39253    0.42732    0.63347
    7.000    -3.586000    -3.678000    -3.373000    -3.493000    2.426000    0.000000     1.177000     6.200000    -1.024000    0.096680    0.000000     0.001057    0.000000     8.290000    -0.366000    772.820000     -0.000070    -0.001375    0.52963    0.39481    0.41907    0.62962
    7.500    -3.835000    -3.936000    -3.636000    -3.720000    2.384000    0.000000     1.162000     6.200000    -1.019000    0.111600    0.000000     0.000975    0.000000     7.810000    -0.338000    770.950000     -0.000007    -0.001371    0.52521    0.39851    0.41093    0.62800
    8.000    -4.068000    -4.175000    -3.894000    -3.932000    2.344000    0.000000     1.152000     6.200000    -1.016000    0.124700    0.000000     0.000923    0.000000     7.370000    -0.317000    770.100000     0.000000     -0.001368    0.50744    0.40286    0.40174    0.62596
    8.500    -4.292000    -4.402000    -4.142000    -4.137000    2.308000    0.000000     1.138000     6.200000    -1.012000    0.137700    0.000000     0.000895    0.000000     6.800000    -0.303000    768.530000     0.000000     -0.001368    0.49611    0.41629    0.39884    0.61769
    9.000    -4.500000    -4.609000    -4.392000    -4.330000    2.258000    0.000000     1.142000     6.200000    -1.013000    0.150200    0.000000     0.000885    0.000000     6.430000    -0.292000    768.710000     0.000000     -0.001366    0.49300    0.41771    0.38229    0.60829
    9.500    -4.689000    -4.800000    -4.605000    -4.509000    2.221000    0.000000     1.158000     6.200000    -1.013000    0.157900    0.000000     0.000888    0.000000     6.130000    -0.284000    771.660000     0.000000     -0.001363    0.48988    0.41800    0.37895    0.59272
    10.00    -4.870000    -4.989000    -4.795000    -4.668000    2.187000    0.000000     1.158000     6.200000    -1.015000    0.160100    0.000000     0.000896    0.000000     5.930000    -0.276700    775.000000     0.000000     -0.001360    0.48361    0.41840    0.37531    0.58136
    """)


gsim_aliases['StewartEtAl2016RegCHN'] = '[StewartEtAl2016]\nregion="CHN"'
gsim_aliases['StewartEtAl2016RegJPN'] = '[StewartEtAl2016]\nregion="JPN"'
gsim_aliases['StewartEtAl2016NoSOF'] = '[StewartEtAl2016]\nsof=false'
gsim_aliases['StewartEtAl2016CHNNoSOF'] = \
    '[StewartEtAl2016]\nregion="CHN"\nsof=false'
gsim_aliases['StewartEtAl2016JPNNoSOF'] = \
    '[StewartEtAl2016]\nregion="JPN"\nsof=false'
