#!/bin/sh

cd unit
./gocad_vessel_test.py
[ $? -ne 0 ] && exit 1
cd ../regression
./reg_run.sh
cd ../../lib/db
./db_tables.py

