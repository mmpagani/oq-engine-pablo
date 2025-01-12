NNParametric
============

+----------------+----------------------+
| checksum32     | 1_631_764_188        |
+----------------+----------------------+
| date           | 2022-03-17T11:22:44  |
+----------------+----------------------+
| engine_version | 3.14.0-gitaed816bf7b |
+----------------+----------------------+
| input_size     | 4_451                |
+----------------+----------------------+

num_sites = 1, num_levels = 19, num_rlzs = 1

Parameters
----------
+---------------------------------+----------------------------------------+
| parameter                       | value                                  |
+---------------------------------+----------------------------------------+
| calculation_mode                | 'preclassical'                         |
+---------------------------------+----------------------------------------+
| number_of_logic_tree_samples    | 0                                      |
+---------------------------------+----------------------------------------+
| maximum_distance                | {'default': [[2.5, 500], [10.2, 500]]} |
+---------------------------------+----------------------------------------+
| investigation_time              | 1.0                                    |
+---------------------------------+----------------------------------------+
| ses_per_logic_tree_path         | 1                                      |
+---------------------------------+----------------------------------------+
| truncation_level                | 2.0                                    |
+---------------------------------+----------------------------------------+
| rupture_mesh_spacing            | 5.0                                    |
+---------------------------------+----------------------------------------+
| complex_fault_mesh_spacing      | 5.0                                    |
+---------------------------------+----------------------------------------+
| width_of_mfd_bin                | 0.1                                    |
+---------------------------------+----------------------------------------+
| area_source_discretization      | 5.0                                    |
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
+----------------------+---------------------+-----------+------------+------------+
| trt_smr              | gsims               | distances | siteparams | ruptparams |
+----------------------+---------------------+-----------+------------+------------+
| Active Shallow Crust | [BooreAtkinson2008] | rjb       | vs30       | mag rake   |
+----------------------+---------------------+-----------+------------+------------+

Slowest sources
---------------
+-----------+------+-----------+-----------+--------------+
| source_id | code | calc_time | num_sites | eff_ruptures |
+-----------+------+-----------+-----------+--------------+
| test      | N    | 0.0       | 1         | 1            |
+-----------+------+-----------+-----------+--------------+

Computation times by source typology
------------------------------------
+------+-----------+-----------+--------------+---------+
| code | calc_time | num_sites | eff_ruptures | weight  |
+------+-----------+-----------+--------------+---------+
| N    | 0.0       | 1         | 1            | 2.02000 |
+------+-----------+-----------+--------------+---------+

Information about the tasks
---------------------------
+--------------------+--------+---------+--------+-----------+---------+---------+
| operation-duration | counts | mean    | stddev | min       | max     | slowfac |
+--------------------+--------+---------+--------+-----------+---------+---------+
| preclassical       | 2      | 0.00210 | 90%    | 2.084E-04 | 0.00398 | 1.90059 |
+--------------------+--------+---------+--------+-----------+---------+---------+
| read_source_model  | 1      | 0.09495 | nan    | 0.09495   | 0.09495 | 1.00000 |
+--------------------+--------+---------+--------+-----------+---------+---------+

Data transfer
-------------
+-------------------+------------------------------------------+----------+
| task              | sent                                     | received |
+-------------------+------------------------------------------+----------+
| read_source_model |                                          | 4.77 KB  |
+-------------------+------------------------------------------+----------+
| split_task        | args=1.02 MB elements=4.94 KB func=132 B | 0 B      |
+-------------------+------------------------------------------+----------+
| preclassical      |                                          | 6.92 KB  |
+-------------------+------------------------------------------+----------+

Slowest operations
------------------
+---------------------------+-----------+-----------+--------+
| calc_50511, maxmem=1.9 GB | time_sec  | memory_mb | counts |
+---------------------------+-----------+-----------+--------+
| importing inputs          | 0.20711   | 0.0       | 1      |
+---------------------------+-----------+-----------+--------+
| composite source model    | 0.20147   | 0.0       | 1      |
+---------------------------+-----------+-----------+--------+
| total read_source_model   | 0.09495   | 0.0       | 1      |
+---------------------------+-----------+-----------+--------+
| total preclassical        | 0.00398   | 0.56641   | 1      |
+---------------------------+-----------+-----------+--------+
| weighting sources         | 0.00307   | 0.0       | 1      |
+---------------------------+-----------+-----------+--------+
| splitting sources         | 4.473E-04 | 0.0       | 1      |
+---------------------------+-----------+-----------+--------+