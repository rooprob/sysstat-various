
pid=$1
path=$2

file="strace-${pid}.trace"

strace -C -o $path/$file -T -ttt -p $pid
