#!/usr/bin/perl -w
#
#9319 1358614002.659924 strlen("idna")                                                                                                              = 4 <0.000271>
#9319 1358614002.660388 strlen("idna")                                                                                                              = 4 <0.000270>
#9319 1358614002.660852 memcmp(0x13b53e4, 0x3191e04, 4, 0xa5e53d233ccc87fc, 0)                                                                      = 0 <0.000277>
#9319 1358614002.661386 strchr("O|n:split", ':')                                                                                                    = ":split" <0.000272>
#9319 1358614002.661858 realloc(NULL, 1104)                                                                                                         = 0x032d7540 <0.000256>
#9319 1358614002.662324 memcpy(0x030f5e68, "h", 24)                                                                                                 = 0x030f5e68 <0.000255>
#9319 1358614002.662774 memcpy(0x030f5e68, "a", 36)                                                                                                 = 0x030f5e68 <0.000256>
#9319 1358614002.663699 realloc(NULL, 32)                                                                                                           = 0x032e0170 <0.000341>
#9319 1358614002.664256 free(0x032d7540)                                                                                                            = <void> <0.000284>
#9319 1358614002.664748 realloc(NULL, 1104)                                                                                                         = 0x032d7540 <0.000426>
#9319 1358614002.665396 memcpy(0x021b6250, "d", 24)                                                                                                 = 0x021b6250 <0.000282>
#9319 1358614002.665888 free(0x032d7540)                                                                                                            = <void> <0.000286>
#9319 1358614002.666392 memcpy(0x021b66d0, "c", 12)                                                                                                 = 0x021b66d0 <0.000283>
#9319 1358614002.666893 strchr("|ss:encode", ':')                                                                                                   = ":encode" <0.000311>
#9319 1358614002.667417 strlen("ascii")                                                                                                             = 5 <0.000295>
#9319 1358614002.667920 strlen("ascii")                                                                                                             = 5 <0.000328>
#9319 1358614983.716740 ERR_get_state(0x3aeb8e0, 568, 256, 0, 36 <unfinished ...>
#9319 1358614983.721229 <... ERR_get_state resumed> ) = 0x318f7a0 <0.004447>
use strict;

my %collapsed;
my $headerlines = 3;

sub remember_stack {
	my ($stack, $count) = @_;
	$collapsed{$stack} += $count;
}

my $nr = 0;
my @stack;

my $snap = 60 ;
my $last = 0;
my $count = 0;
my $total_count = 0;
my $unfinished = 0 ;
my %completed ;
my $min_time = 0;
my $max_time = 0;
foreach (<>) {
    chomp ;

    if ( /SIGCHLD/ ) {
        next;
    }
    if ( /unfinished/ ) {
        $unfinished ++ ;
        next;
    }

    $total_count ++ ;

    if (! /^(\d+) ([\d\.]+) (.+)\s+= ((?:\S+|".*"|'.*')) (<[\d\.]+>)$/) {
        die("unable to parse $_");
    }

    my ($pid, $time, $func, $result, $secs) = ($1, $2, $3, $4, $5);

    # printf("debug: %d %s %s %s %s\n", $pid, $time, $func, $result, $secs);

    $time = int($time  / $snap) * $snap;

    if ($time > $max_time) {
        $max_time = $time;
    }
    if ($min_time == 0) {
        $min_time = $time;
    }
    $completed{$time} ++  ;

=snip
    if ($time ne $last) {
        if ($last != 0) {
            printf("%d %d\n", $time, $count);

            $count = 1;

            $last = $time;
        } else {
            $last = $time;
            $count = 1;
        }
    } else {
        $count ++ ;
    }
=cut

}

printf("parsed total %d syscalls, %d unfinished\n", $total_count, $unfinished);
for (my $idx = $min_time ; $idx < $max_time + $snap; $idx = $idx + $snap) {
    my $r = 0;
    if (exists($completed{$idx})) {
        $r = $completed{$idx};
    }
    printf("%d,%s,%d\n", $idx, scalar gmtime($idx), $r);
}
