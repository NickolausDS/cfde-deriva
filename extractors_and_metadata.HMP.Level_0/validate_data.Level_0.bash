#!/bin/bash

##################################################################################################
# Please install goodtables before running: https://github.com/frictionlessdata/goodtables-py
# 
# NOTE: 'MISSING HEADER' ERRORS WILL BE GENERATED for all TSVs with no records in them (i.e. TSVs
# containing only header lines). If the tables associated with the offending TSVs are supposed to
# be empty, then these errors can and should be ignored; the table format is valid despite
# goodtables' complaints.
##################################################################################################

dataDir=002_HMP__C2M2_Level_0_preload__preBag_output_files

goodtables validate -o data_validation_report.Level_0.txt $dataDir/C2M2_Level_0.datapackage.json

