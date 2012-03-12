#! /bin/bash

dev_appserver.py --high_replication --use_sqlite "$@" $(dirname $0)
