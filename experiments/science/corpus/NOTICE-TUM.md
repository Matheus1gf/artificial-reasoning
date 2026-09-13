# TUM RGB-D trajectory attribution

`tum-fr1-xyz-groundtruth.txt` is an unchanged copy of the measured ground-truth
trajectory from TUM RGB-D, sequence **fr1/xyz**. Authors: Jürgen Sturm, Nikolas
Engelhard, Felix Endres, Wolfram Burgard and Daniel Cremers. Publication:
*A Benchmark for the Evaluation of RGB-D SLAM Systems*, IROS 2012.

The [current primary dataset page](https://cvg.cit.tum.de/data/datasets/rgbd-dataset)
licenses benchmark data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The 2012 paper mentioned the earlier CC BY 3.0 release; this repository records
the current upstream license verified on 12 September 2026. No endorsement is implied.

[Primary numeric download](https://cvg.cit.tum.de/rgbd/dataset/freiburg1/rgbd_dataset_freiburg1_xyz-groundtruth.txt)
and [paper](https://cvg.cit.tum.de/_media/spezial/bib/sturm12iros.pdf).
The raw text is unchanged. Our derived reports select timestamps, subtract a
local time origin and evaluate each world coordinate independently. They are
our analysis, not results or conclusions published by the original authors.

The versioned metadata describes the measurement system, units, conditions and
empirical error bounds. The trajectory was recorded for visual SLAM evaluation;
it is not a controlled force experiment and does not identify a new physical law.
