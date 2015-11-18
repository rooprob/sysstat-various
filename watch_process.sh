#!/bin/bash

#set -x

TICK=1

if [[ "$1" != *[!0-9]* ]]; then
  proc=$1

else
  proc=`pgrep $1 | grep -v -E '($0|grep)'`
  rc=$?
  if [ $rc != 0 ] ; then
      echo "info: no pid found for $1" >&2
      exit 1
  fi 
fi

if [[ "$proc" = *[!0-9]* ]]; then
  echo "error: a single pid is required "$proc"" >&2
  exit 2
fi

while [ 1 ]
do
    if [ "$?" = 0 ]; then 
        MEM=`ps -o rss= -p $proc | tr -d ' '`

        time=$(date +'%s')
        date=$(date --rfc-3339=seconds)

        echo -e "$date\t$time\t$MEM"
    fi 
    sleep $TICK

    if [ ! -e "/proc/$proc" ] ; then
	exit 0
    fi

done | tee -a watch_process.log
