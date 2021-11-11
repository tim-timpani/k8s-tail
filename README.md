# k8s_tail
Utility script to tail one or more container logs to file(s)
* Multiple logs can be followed with a single command. 
* Use regex patterns to match pod and/or container names.
* Limit pods by namespace
* See all logs in a single live updated timeline with 
log viewer software such as lnav.

###Usage
* Provide a top level directory to save the log files
either through environment variable LOG_DIRECTORY or
by command line option -l, --logdir
* A subdirectory will be created under the top level log
directory where all logs will written to.
* Container logs will be "followed" based on command line
options. Use --help for details
