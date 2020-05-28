SELECT DISTINCT
  fdb.file_id_namespace,
  fdb.file_id,
  b.assay_type
FROM file_describes_biosample fdb
JOIN biosample b
  ON (fds.biosample_id_namespace = b.id_namespace AND fds.biosample_id = b.id)
WHERE b.assay_type IS NOT NULL