#!/bin/bash

recording=$1

(
echo "set terminal png size 1000,600"
echo "set datafile separator \",\""
echo "set xlabel \"Minutes Elapsed\""
echo "set ylabel \"Memory\""
echo "set xdata time"
echo "set timefmt \"%s\""
echo "set format x \"%H:%M\""     # or anything else
echo "set title \"Command RSS\""
echo "plot \"$recording\" using 2:3 t \"RSS\" w line "
) | gnuplot > ${recording}.png
