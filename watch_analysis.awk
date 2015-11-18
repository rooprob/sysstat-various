# ts $1	          $2         $3                   port $4 rss $5  mode $6 count $7
# 1358103697      2013-01-13 19:01:37+00:00       2000    41968   LISTEN  1

BEGIN {

  SNAP = 1

}
// {
    #print "NF = ", NF
    #for (i = 1; i <= NF; i++) {
    #    printf("$%d = <%s>\n", i, $i)
    #}
    port = $4
    rss = $5
    status_code = $6
    count = $7

    timestamp = $1
    timestamp = int(timestamp / SNAP) * SNAP

    key=timestamp","status_code
    #printf ("%s year %d %d %d %d %d %s\n", $1, year, month, day, hour, min, key)

    if (inflight[key,"count"]) {
        inflight[key,"count"] ++
        inflight[key,"rss"] += rss
    } else {
        inflight[key,"count"] = count
        inflight[key,"rss"] = rss
        keys[key] = 1
        timestamps[timestamp] = 1
        statuscodes[status_code] = 1
    }

}
END {

    # create header
    sn = asorti(statuscodes, s_statuscodes)
    printf("timestamp")
    for (idx = 1; idx <= sn; idx ++) {
        printf(",%s", s_statuscodes[idx])
    }
    printf("\n")

    tn = asorti(timestamps, s_timestamps)
    for (idx = 1; idx <= tn; idx ++) {
        timestamp = s_timestamps[idx]
        #printf("%d", timestamp)
        printf("%s", strftime("%a %b %e %H:%M:%S %Z %Y", timestamp))
        for (jdx = 1; jdx <= sn; jdx ++) {
            status_code = s_statuscodes[jdx]
            key = timestamp","status_code
            if (inflight[key,"count"]) {

                # printf(",%d", inflight[key,"count"])
                printf(",%d", inflight[key,"count"])
            } else {
                printf(",0")
            }
        }
        printf("\n")
    }

}
