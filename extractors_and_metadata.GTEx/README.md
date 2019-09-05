# Prototype extract/transform script from GTEx v7 metadata to draft C2M2 core metadata standard

## Contents

This directory contains the prototype GTEx extractor script along with
- a Table-Schema JSON file describing the output
- raw input data from GTEx
- some auxiliary files mapping GTEx terminology to terms in selected controlled vocabularies
- a gzipped tarball containing example output
- an ER diagram (based on but different from Karl's working draft) precisely describing output structure
  - ...except for DCC-specific auxiliary data, which isn't drawn: this is encoded as a flat table ("AuxiliaryData.tsv") of 4-tuples: "ObjectType", "ObjectID", "DataDescription" and "Value", so that each record generically links some bit of metadata to some existing object [like a BioSample or a Subject] within the C2M2 model).

## Dependencies

- A working version of Perl5
- 'bdbag' needs to be accessible via $PATH

## Design notes that will definitely need to be addressed

- Simplifying constraint: this implementation is agnostic to public/private data distinctions, a deficiency which is going to need to be resolved downstream, at least for GTEx. As far as I can tell, all but the most superficial of their actual data files (e.g. sequence FASTQ, CRAM alignment reports) are protected, as is information regarding names and access locations/URLs for those files. The file location data I'm extracting with this prototype script was specifically dumped by GTEx people last year to facilitate a prior version of our ingest attempt: consultation will need to be done with GTEx to figure out a formal way of indexing files (down to their names, which don't contain protected info, and hopefully URLs) for search/discovery while preserving whatever data-protection gatekeepers need to remain in place between users and the files themselves.

- I've created a basic hierarchy of Datasets by hand (top_level -> alignment-file_data -> { RNA-Seq alignment files, WGS alignment files}). There are too many different possibilities for slicing this data into subsets to yield an obvious automatic solution to Dataset construction: consultation will need to happen at some level to establish, in advance, a map from GTEx logical containment structures (from "nucleic acid isolation batch ID" all the way up to "version 7 data release") to C2M2 Datasets.



## Design notes that will may not need to be addressed

- External CVs currently in use:
  - OBI (BioSample.sample_type, DataEvent.method)
  - EDAM (File.information_type, File.file_format)
  - NCBI Taxonomy (SubjectTaxonomy.NCBITaxonID)
  
  These are currently implemented as fields containing full URLs referencing the relevant terms.

- The Table-Schema implements the Frictionless Data "tabular data package" spec (https://frictionlessdata.io/specs/tabular-data-package/), which contains instances of that group's "table schema" object (https://frictionlessdata.io/specs/table-schema/).

- I've abandoned JSON as a serialization format: a collection of TSVs is built instead, representing table data defined in my version of the draft core metadata model (included here as a PNG)
