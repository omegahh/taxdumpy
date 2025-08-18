#!/bin/bash

taxdumpy cache -f taxids.list

head ~/.taxonkit/delnodes.dmp >delnodes.dmp
cp ~/.taxonkit/division.dmp division.dmp

awk 'NR==FNR{key[$0]=1; next} $3 in key' kept_taxids.list ~/.taxonkit/merged.dmp >merged.dmp
awk 'NR==FNR{key[$0]=1; next} $1 in key' kept_taxids.list ~/.taxonkit/names.dmp >names.dmp
awk 'NR==FNR{key[$0]=1; next} $1 in key' kept_taxids.list ~/.taxonkit/nodes.dmp >nodes.dmp
