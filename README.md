# k8s_tail
Utility script to tail one or more container logs to file(s)
* Multiple logs can be followed with a single command. 
* Use regex patterns to match pod and/or container names.
* Limit pods by namespace
* See all logs in a single live updated timeline with 
log viewer software such as lnav.
* Logs can be retained or just written to a temporary directory

###Usage
* Provide a top level directory to save the log files
either through environment variable LOG_DIRECTORY or
by command line option -l, --logdir
* A subdirectory will be created under the top level log
directory where all logs will written to.
* Container logs will be "followed" based on command line
options. Use --help for details
* Use the -v, --view option to automatically launch lnav
(or another viewer overrriden by LOG_VIEWER env var) and
stop the log tailing when the viewer exits.
* Specify - for the -l, --logdir option to save logs to a
temporary directory, view the logs, then cleanup the log
files when the viewer exists. The -v, --view option will be
automatically enabled when using this option.

###Examples
Below are some examples. use the --help option for more
details

#### Retain logs
To retain all the logs from all containers in the database
namespace into a subdirectory under ~/logs. The current
default kueconfig file is used in this example
> k8s-tail -l ~/logs -n database

Then enter "stop" at the prompt to stop tailing the logs

#### Temporary logs
To write the container logs from all container names matching
regex ^maria in all namespace into a temp directory just
for immediate viewing (The kubeconfig is also specified here)
>k8s-tail -l - -c '^maria' -k ~/.kube/my_cluster_config

Just exit the log viewer to stop the log tailing and delete
the log files.
