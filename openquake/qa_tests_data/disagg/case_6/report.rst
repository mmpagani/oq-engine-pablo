GEM model for PAC, 0.10 in 50 years, Suva, testing IDL
======================================================

+----------------+----------------------+
| checksum32     | 335_220_095          |
+----------------+----------------------+
| date           | 2022-03-17T11:26:39  |
+----------------+----------------------+
| engine_version | 3.14.0-gitaed816bf7b |
+----------------+----------------------+
| input_size     | 30_184               |
+----------------+----------------------+

num_sites = 1, num_levels = 20, num_rlzs = 3

Parameters
----------
+---------------------------------+----------------------------------------+
| parameter                       | value                                  |
+---------------------------------+----------------------------------------+
| calculation_mode                | 'preclassical'                         |
+---------------------------------+----------------------------------------+
| number_of_logic_tree_samples    | 0                                      |
+---------------------------------+----------------------------------------+
| maximum_distance                | {'default': [[2.5, 300], [10.2, 300]]} |
+---------------------------------+----------------------------------------+
| investigation_time              | 1.0                                    |
+---------------------------------+----------------------------------------+
| ses_per_logic_tree_path         | 1                                      |
+---------------------------------+----------------------------------------+
| truncation_level                | 3.0                                    |
+---------------------------------+----------------------------------------+
| rupture_mesh_spacing            | 5.0                                    |
+---------------------------------+----------------------------------------+
| complex_fault_mesh_spacing      | 10.0                                   |
+---------------------------------+----------------------------------------+
| width_of_mfd_bin                | 0.1                                    |
+---------------------------------+----------------------------------------+
| area_source_discretization      | 10.0                                   |
+---------------------------------+----------------------------------------+
| pointsource_distance            | {'default': '1000'}                    |
+---------------------------------+----------------------------------------+
| ground_motion_correlation_model | None                                   |
+---------------------------------+----------------------------------------+
| minimum_intensity               | {}                                     |
+---------------------------------+----------------------------------------+
| random_seed                     | 23                                     |
+---------------------------------+----------------------------------------+
| master_seed                     | 123456789                              |
+---------------------------------+----------------------------------------+
| ses_seed                        | 42                                     |
+---------------------------------+----------------------------------------+

Input files
-----------
+-------------------------+--------------------------+
| Name                    | File                     |
+-------------------------+--------------------------+
| gsim_logic_tree         | `gmmLT.xml <gmmLT.xml>`_ |
+-------------------------+--------------------------+
| job_ini                 | `job.ini <job.ini>`_     |
+-------------------------+--------------------------+
| source_model_logic_tree | `ssmLT.xml <ssmLT.xml>`_ |
+-------------------------+--------------------------+

Required parameters per tectonic region type
--------------------------------------------
+----------------------+---------------------------------------------------------+-------------+-------------------------+------------------------------+
| trt_smr              | gsims                                                   | distances   | siteparams              | ruptparams                   |
+----------------------+---------------------------------------------------------+-------------+-------------------------+------------------------------+
| Active Shallow Crust | [ZhaoEtAl2006Asc] [BooreAtkinson2008] [ChiouYoungs2008] | rjb rrup rx | vs30 vs30measured z1pt0 | dip hypo_depth mag rake ztor |
+----------------------+---------------------------------------------------------+-------------+-------------------------+------------------------------+

Slowest sources
---------------
+-----------+------+-----------+-----------+--------------+
| source_id | code | calc_time | num_sites | eff_ruptures |
+-----------+------+-----------+-----------+--------------+
| 39        | S    | 0.0       | 6         | 61           |
+-----------+------+-----------+-----------+--------------+
| 36        | S    | 0.0       | 6         | 67           |
+-----------+------+-----------+-----------+--------------+
| 32        | S    | 0.0       | 7         | 80           |
+-----------+------+-----------+-----------+--------------+
| 28        | S    | 0.0       | 7         | 55           |
+-----------+------+-----------+-----------+--------------+
| 19        | S    | 0.0       | 7         | 86           |
+-----------+------+-----------+-----------+--------------+

Computation times by source typology
------------------------------------
+------+-----------+-----------+--------------+--------+
| code | calc_time | num_sites | eff_ruptures | weight |
+------+-----------+-----------+--------------+--------+
| S    | 0.0       | 33        | 349          | 387.1  |
+------+-----------+-----------+--------------+--------+

Information about the tasks
---------------------------
+--------------------+--------+---------+--------+-----------+---------+---------+
| operation-duration | counts | mean    | stddev | min       | max     | slowfac |
+--------------------+--------+---------+--------+-----------+---------+---------+
| preclassical       | 2      | 0.60294 | 99%    | 2.127E-04 | 1.20566 | 1.99965 |
+--------------------+--------+---------+--------+-----------+---------+---------+
| read_source_model  | 1      | 0.01992 | nan    | 0.01992   | 0.01992 | 1.00000 |
+--------------------+--------+---------+--------+-----------+---------+---------+

Data transfer
-------------
+-------------------+-------------------------------------------+----------+
| task              | sent                                      | received |
+-------------------+-------------------------------------------+----------+
| read_source_model |                                           | 37.98 KB |
+-------------------+-------------------------------------------+----------+
| split_task        | args=1.02 MB elements=39.59 KB func=132 B | 0 B      |
+-------------------+-------------------------------------------+----------+
| preclassical      |                                           | 50.87 KB |
+-------------------+-------------------------------------------+----------+

Slowest operations
------------------
+---------------------------+----------+-----------+--------+
| calc_50594, maxmem=1.9 GB | time_sec | memory_mb | counts |
+---------------------------+----------+-----------+--------+
| total preclassical        | 1.20566  | 1.22656   | 5      |
+---------------------------+----------+-----------+--------+
| weighting sources         | 0.84999  | 0.0       | 33     |
+---------------------------+----------+-----------+--------+
| importing inputs          | 0.35884  | 0.16406   | 1      |
+---------------------------+----------+-----------+--------+
| composite source model    | 0.35175  | 0.16406   | 1      |
+---------------------------+----------+-----------+--------+
| splitting sources         | 0.10634  | 0.18750   | 5      |
+---------------------------+----------+-----------+--------+
| total read_source_model   | 0.01992  | 0.01953   | 1      |
+---------------------------+----------+-----------+--------+