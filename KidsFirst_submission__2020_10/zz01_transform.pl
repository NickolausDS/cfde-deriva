#!/usr/bin/perl

use strict;

$| = 1;

# PARAMETERS

my $inDir = '000_original';

my $stubDir = '001_static_stubs.some_newly_created_with_abhijna';

my $outDir = 'KF_C2M2_submission';

# EXECUTION

foreach my $unmodFile ( 'anatomy.tsv', 'data_type.tsv', 'file_format.tsv', 'id_namespace.tsv', 'ncbi_taxonomy.tsv' ) {
   
   system("cp $inDir/$unmodFile $outDir");
}

foreach my $staticStub ( 'assay_type.tsv', 'biosample_in_collection.tsv', 'biosample_from_subject.tsv', 'collection.tsv', 'collection_defined_by_project.tsv', 'collection_in_collection.tsv',
                           'file_describes_biosample.tsv', 'file_describes_subject.tsv', 'file_in_collection.tsv', 'project.tsv', 'project_in_project.tsv', 'subject_in_collection.tsv',
                           'subject_role_taxonomy.tsv', 'primary_dcc_contact.tsv',
                           'biosample.tsv', 'subject.tsv', 'C2M2_Level_1.datapackage.json' ) {
   
   system("cp $stubDir/$staticStub $outDir");
}

my $assayType = {};

open IN, "<000_original/biosample.tsv" or die("Can't open 000_original/biosample.tsv for reading.\n");

while ( chomp( my $line = <IN> ) ) {
   
   my @fields = split(/\t/, $line);

   my $id = $fields[1];

   my $at_val = $fields[6];

   if ( $at_val ne '' ) {
      
      $assayType->{$id} = $at_val;
   }
}

close IN;

open IN, "<001_static_stubs.some_newly_created_with_abhijna/file_describes_biosample.tsv" or die("Can't open 001_static_stubs.some_newly_created_with_abhijna/file_describes_biosample.tsv for reading.\n");

my $header = <IN>;

my $fileAssayType = {};

while ( chomp( my $line = <IN> ) ) {
   
   my ( $fileNS, $fileID, $sampleNS, $sampleID ) = split(/\t/, $line);

   if ( exists( $assayType->{$sampleID} ) ) {
      
      $fileAssayType->{$fileID} = $assayType->{$sampleID};
   }
}

close IN;

open IN, "<$inDir/file.tsv" or die("Can't open $inDir/file.tsv for reading.\n");

open OUT, ">$outDir/file.tsv" or die("Can't open $outDir/file.tsv for writing.\n");

$header = <IN>;

print OUT join("\t",
                     'id_namespace',
                     'local_id',
                     'project_id_namespace',
                     'project_local_id',
                     'persistent_id',
                     'creation_time',
                     'size_in_bytes',
                     'uncompressed_size_in_bytes',
                     'sha256',
                     'md5',
                     'filename',
                     'file_format',
                     'data_type',
                     'assay_type',
                     'mime_type' ) . "\n";

while ( chomp( my $line = <IN> ) ) {
   
   my ( $id_ns, $local_id, $project_id_ns, $project_local_id, $persistent_id, $creation_time, $size_in_bytes, $sha256, $md5, $filename, $file_format, $data_type ) = split(/\t/, $line);

   my $at_val = '';

   if ( exists( $fileAssayType->{$local_id} ) ) {
      
      $at_val = $fileAssayType->{$local_id};
   }

   print OUT "$id_ns\t$local_id\t$project_id_ns\t$project_local_id\t$persistent_id\t$creation_time\t";

   print OUT "$size_in_bytes\t\t$sha256\t$md5\t$filename\t$file_format\t$data_type\t$at_val\tapplication/octet-stream\n";
}

close OUT;

close IN;


