#!/usr/bin/python3

# This script assumes latest deriva-py/master library
# talking to latest ermrest/master server

import sys
import os
import json
from deriva.core import ErmrestCatalog, urlquote
from deriva.core.datapath import Min, Max, Cnt, CntD, Avg, Sum, Bin

######
# utility functions to idempotently build up the path in a StatsQuery object
#
# uses level1_stats data cube, which is based on this core-entity query path:
#
#   file -- file-describes-biosample -- biosample -- biosample-from-subject -- subject
#
# summarized into groups based on metadata combinations
#
#   file -- assay_type, data_type, file_format
#   biosample -- anatomy
#   subject -- subject_role_taxonomy -- ncbi_taxonomy, subject_role, subject_granularity
#   [stats entity] -- project
#   [stats entity] -- root project
#
# with each group containing num_files, num_bytes, num_biosamples, num_subjects.
#
# to retrieve stats, we choose our own dimensional grouping (as a subset of the
# available grouping dimensions) and sum those existing metrics to collapse
# results into our more coarse-grained groups.
#
# the subproject dimension joins extra structure to the project concept of the data cube.
#
# also, we join the vocab tables to get human-readable names for the dimensional concepts
#

def _add_anatomy_leaf(queryobj, show_nulls=False, **kwargs):
    if 'anatomy' in queryobj.path.table_instances:
        return
    anatomy = queryobj.helper.builder.CFDE.anatomy
    queryobj.path = queryobj.path.link(
        anatomy,
        on=( queryobj.path.level1_stats.anatomy_id == anatomy.id ),
        join_type= 'left' if show_nulls else ''
    )

def _add_assaytype_leaf(queryobj, show_nulls=False, **kwargs):
    if 'assay_type' in queryobj.path.table_instances:
        return
    assay_type = queryobj.helper.builder.CFDE.assay_type
    queryobj.path = queryobj.path.link(
        assay_type,
        on=( queryobj.path.level1_stats.assay_type_id == assay_type.id ),
        join_type= 'left' if show_nulls else ''
    )

def _add_datatype_leaf(queryobj, show_nulls=False, **kwargs):
    if 'data_type' in queryobj.path.table_instances:
        return
    data_type = queryobj.helper.builder.CFDE.data_type
    queryobj.path = queryobj.path.link(
        data_type,
        on=( queryobj.path.level1_stats.data_type_id == data_type.id ),
        join_type= 'left' if show_nulls else ''
    )

def _add_species_leaf(queryobj, show_nulls=False, **kwargs):
    if 'species' in queryobj.path.table_instances:
        return
    species = queryobj.helper.builder.CFDE.ncbi_taxonomy.alias('species')
    queryobj.path = queryobj.path.link(
        species,
        on=( queryobj.path.level1_stats.species_id == species.id ),
        join_type= 'left' if show_nulls else ''
    )

def _add_rootproject_leaf(queryobj, show_nulls=False, **kwargs):
    """Idempotently add root project concept to path"""
    # ignore show_nulls since project is always attributed
    if 'subproject' in queryobj.path.table_instances:
        raise TypeError('Cannot combine subproject and project_root dimensions')

    if 'root_project' in queryobj.path.table_instances:
        return

    root_project = queryobj.helper.builder.CFDE.project.alias('root_project')
    queryobj.path = queryobj.path.link(
        root_project,
        on=( (queryobj.path.level1_stats.root_project_id_namespace == root_project.id_namespace)
             & (queryobj.path.level1_stats.root_project_local_id == root_project.local_id) )
    )

def _add_subproject_leaf(queryobj, show_nulls=False, **kwargs):
    """Idempotently add root project concept to path"""
    # ignore show_nulls since project is always attributed
    try:
        parent_project_RID = kwargs['parent_project_RID']
    except KeyError:
        raise TypeError('Missing required parent_project_RID keyword argument in StatsQuery.dimension("subproject", **kwargs) call')

    if 'root_project' in queryobj.path.table_instances:
        raise TypeError('Cannot combine subproject and project_root dimensions')

    level1_stats = queryobj.path.level1_stats
    pipt = queryobj.helper.builder.CFDE.project_in_project_transitive.alias('pipt')
    pip = queryobj.helper.builder.CFDE.project_in_project.alias('pip')
    subproject = queryobj.helper.builder.CFDE.project.alias('subproject')
    parentproj = queryobj.helper.builder.CFDE.project.alias('parentproj')

    queryobj.path = queryobj.path.link(
        pipt,
        on=( (level1_stats.project_id_namespace == pipt.member_project_id_namespace)
             & (level1_stats.project_local_id == pipt.member_project_local_id) )
    ).link(
        pip,
        on=( (queryobj.path.pipt.leader_project_id_namespace == pip.child_project_id_namespace)
             & (queryobj.path.pipt.leader_project_local_id == pip.child_project_local_id) )
    ).link(
        parentproj,
        on=( (queryobj.path.pip.parent_project_id_namespace == parentproj.id_namespace)
             & (queryobj.path.pip.parent_project_local_id == parentproj.local_id) )
    ).filter(
        queryobj.path.parentproj.RID == parent_project_RID
    ).link(
        subproject,
        on=( (queryobj.path.pipt.leader_project_id_namespace == subproject.id_namespace)
             & (queryobj.path.pipt.leader_project_local_id == subproject.local_id) )
    )

class StatsQuery (object):
    """C2M2 statistics query generator

    Construct with a DashboardQueryHelper instance to bind to a
    catalog, select base entity for statistics, and select optional
    dimensions for multi-dimensional grouping of results.

    StatsQuery(helper)
    .entity('file')
    .dimension('data_type')
    .dimension('project_root')
    .fetch()

    Exactly one entity MUST be configured. Zero or more dimensions MAY
    be configured.

    """

    # define supported keys, mapped to implementation bits...
    supported_entities = {
        'file': [
            lambda path: Sum(path.level1_stats.num_files).alias('num_files'),
            lambda path: Sum(path.level1_stats.num_bytes).alias('num_bytes'),
        ],
        'biosample': [
            lambda path: Sum(path.level1_stats.num_biosamples).alias('num_biosamples'),
        ],
        'subject': [
            lambda path: Sum(path.level1_stats.num_subjects).alias('num_subjects'),
        ],
    }
    supported_dimensions = {
        'anatomy': (
            _add_anatomy_leaf, [
                lambda path: path.level1_stats.anatomy_id,
            ], [
                lambda path: path.anatomy.column_definitions['name'].alias('anatomy_name'),
            ]
        ),
        'assay_type': (
            _add_assaytype_leaf, [
                lambda path: path.level1_stats.assay_type_id,
            ], [
                lambda path: path.assay_type.column_definitions['name'].alias('assay_type_name'),
            ]
        ),
        'data_type': (
            _add_datatype_leaf, [
                lambda path: path.level1_stats.data_type_id,
            ], [
                lambda path: path.data_type.column_definitions['name'].alias('data_type_name'),
            ]
        ),
        'species': (
            _add_species_leaf, [
                lambda path: path.species.id.alias('species_id'),
            ], [
                lambda path: path.species.column_definitions['name'].alias('species_name'),
            ]
        ),
        'project_root': (
            _add_rootproject_leaf, [
                lambda path: path.root_project.RID.alias('project_RID'),
            ], [
                lambda path: path.root_project.id_namespace.alias('project_id_namespace'),
                lambda path: path.root_project.local_id.alias('project_local_id'),
                lambda path: path.root_project.column_definitions['name'].alias('project_name'),
            ]
        ),
        'subproject': (
            _add_subproject_leaf, [
                lambda path: path.subproject.RID.alias('project_RID'),
            ], [
                lambda path: path.subproject.id_namespace.alias('project_id_namespace'),
                lambda path: path.subproject.local_id.alias('project_local_id'),
                lambda path: path.subproject.column_definitions['name'].alias('project_name'),
            ],
        ),
    }

    def __init__(self, helper):
        """Construct a StatsQuery builder object

        :param helper: Instance of DashboardQueryHelper
        """
        self.helper = helper
        self.entity_name = None
        self.included_dimensions = set()
        self.path = None
        self.grpk_funcs = []
        self.attr_funcs = []

    def entity(self, entity_name):
        """Select entity which will be source of statistics

        :param entity_name: One of the StatsQuery.supported_entities key strings
        """
        if self.path is not None:
            raise TypeError('Cannot call .entity() method on a StatsQuery instance more than once.')

        try:
            self.attr_funcs.extend(self.supported_entities[entity_name])
            self.entity_name = entity_name
        except KeyError:
            raise ValueError('Unsupported entity_name "%s"' % (entity_name,))

        self.path = self.helper.builder.CFDE.level1_stats.path

        return self

    def dimension(self, dimension_name, show_nulls=True, **kwargs):
        """Configure a grouping dimension

        :param dimension_name: One of the StatsQuery.supported_dimension key strings
        :param show_nulls: Allow null in dimensional outputs when True (default True)
        :param kwargs: Keyword arguments specific to a dimension (see further documentation)

        Dimension-specific keyword arguments:

        :param parent_project_RID: Use sub-projects of specified parent project RID for "subproject" dimension (required)

        """
        if self.path is None:
            raise TypeError('Cannot call .dimension() method on a StatsQuery instance prior to calling .entity() method.')
        if dimension_name in self.included_dimensions:
            raise TypeError('Cannot use dimension_name "%s" more than once in a StatsQuery instance.' % (dimension_name,))

        try:
            add_path_func, grpk_funcs, attr_funcs = self.supported_dimensions[dimension_name]
            self.grpk_funcs.extend(grpk_funcs)
            self.attr_funcs.extend(attr_funcs)
            self.included_dimensions.add(dimension_name)
        except KeyError:
            raise ValueError('Unsupported dimension_name "%s"' % (dimension_name,))

        add_path_func(self, show_nulls=show_nulls, **kwargs)

        return self

    def fetch(self):
        """Fetch results for configured query"""
        if self.path is None:
            raise TypeError('Cannot call .fetch() method on a StatsQuery instance prior to calling .entity() method.')
        if self.grpk_funcs:
            return self.path.groupby(*[
                grpk_func(self.path)
                for grpk_func in self.grpk_funcs
            ]).attributes(*[
                attr_func(self.path)
                for attr_func in self.attr_funcs
            ]).fetch()
        else:
            return self.path.aggregates(*[
                attr_func(self.path)
                for attr_func in self.attr_funcs
            ]).fetch()

class DashboardQueryHelper (object):

    def __init__(self, hostname, catalogid, scheme='https'):
        self.catalog = ErmrestCatalog(scheme, hostname, catalogid)
        self.builder = self.catalog.getPathBuilder()

    def run_demo(self):
        """Run each example query and dump all results as JSON."""
        projects = {
            (row['id_namespace'], row['local_id']): row
            for row in self.list_projects(use_root_projects=True)
        }

        rid_for_parent_proj = projects[('cfde_id_namespace:2', '3a51534abc6e1a5ee6d9cc86c4007b56')]['RID']

        # use list() to convert each ResultSet
        # for easier JSON serialization...
        results = {
            #'list_projects': list(self.list_projects()),
            #'list_root_projects': list(self.list_projects(use_root_projects=True)),
            #'list_datatypes': list(self.list_datatypes()),
            #'list_formats': list(self.list_formats()),

            'root_projects': list(self.list_projects(use_root_projects=True)),
            'subject_stats_assaytype_subproject': list(StatsQuery(self).entity('subject').dimension('assay_type').dimension('subproject', parent_project_RID=rid_for_parent_proj).fetch()),

            'file_stats_anatomy_assaytype': list(StatsQuery(self).entity('file').dimension('anatomy').dimension('assay_type').fetch()),
            'file_stats_anatomy_datatype': list(StatsQuery(self).entity('file').dimension('anatomy').dimension('data_type').fetch()),
            'file_stats_anatomy_species': list(StatsQuery(self).entity('file').dimension('anatomy').dimension('species').fetch()),
            'file_stats_anatomy_project': list(StatsQuery(self).entity('file').dimension('anatomy').dimension('project_root').fetch()),
            'file_stats_assaytype_datatype': list(StatsQuery(self).entity('file').dimension('assay_type').dimension('data_type').fetch()),
            'file_stats_assaytype_species': list(StatsQuery(self).entity('file').dimension('assay_type').dimension('species').fetch()),
            'file_stats_assaytype_project': list(StatsQuery(self).entity('file').dimension('assay_type').dimension('project_root').fetch()),
            'file_stats_datatype_species': list(StatsQuery(self).entity('file').dimension('data_type').dimension('species').fetch()),
            'file_stats_datatype_project': list(StatsQuery(self).entity('file').dimension('data_type').dimension('project_root').fetch()),

            'biosample_stats_anatomy_assaytype': list(StatsQuery(self).entity('biosample').dimension('anatomy').dimension('assay_type').fetch()),
            'biosample_stats_anatomy_datatype': list(StatsQuery(self).entity('biosample').dimension('anatomy').dimension('data_type').fetch()),
            'biosample_stats_anatomy_species': list(StatsQuery(self).entity('biosample').dimension('anatomy').dimension('species').fetch()),
            'biosample_stats_anatomy_project': list(StatsQuery(self).entity('biosample').dimension('anatomy').dimension('project_root').fetch()),
            'biosample_stats_assaytype_datatype': list(StatsQuery(self).entity('biosample').dimension('assay_type').dimension('data_type').fetch()),
            'biosample_stats_assaytype_species': list(StatsQuery(self).entity('biosample').dimension('assay_type').dimension('species').fetch()),
            'biosample_stats_assaytype_project': list(StatsQuery(self).entity('biosample').dimension('assay_type').dimension('project_root').fetch()),
            'biosample_stats_datatype_species': list(StatsQuery(self).entity('biosample').dimension('data_type').dimension('species').fetch()),
            'biosample_stats_datatype_project': list(StatsQuery(self).entity('biosample').dimension('data_type').dimension('project_root').fetch()),

            'subject_stats_anatomy_assaytype': list(StatsQuery(self).entity('subject').dimension('anatomy').dimension('assay_type').fetch()),
            'subject_stats_anatomy_datatype': list(StatsQuery(self).entity('subject').dimension('anatomy').dimension('data_type').fetch()),
            'subject_stats_anatomy_species': list(StatsQuery(self).entity('subject').dimension('anatomy').dimension('species').fetch()),
            'subject_stats_anatomy_project': list(StatsQuery(self).entity('subject').dimension('anatomy').dimension('project_root').fetch()),
            'subject_stats_assaytype_datatype': list(StatsQuery(self).entity('subject').dimension('assay_type').dimension('data_type').fetch()),
            'subject_stats_assaytype_species': list(StatsQuery(self).entity('subject').dimension('assay_type').dimension('species').fetch()),
            'subject_stats_assaytype_project': list(StatsQuery(self).entity('subject').dimension('assay_type').dimension('project_root').fetch()),
            'subject_stats_datatype_species': list(StatsQuery(self).entity('subject').dimension('data_type').dimension('species').fetch()),
            'subject_stats_datatype_project': list(StatsQuery(self).entity('subject').dimension('data_type').dimension('project_root').fetch()),

        }
        print(json.dumps(results, indent=2))

    def list_projects(self, use_root_projects=False, parent_project_RID=None):
        """Return list of projects AKA funded activities

        :param use_root_projects: Only consider root projects (default False)
        :param parent_project_RID: Only consider children of specified project (default None)
        """
        children = self.builder.CFDE.project.alias("children")
        pip1 = self.builder.CFDE.project_in_project.alias('pip1')
        project = self.builder.CFDE.project
        path = children.path
        path = path.link(
            pip1,
            on=( (path.children.id_namespace == pip1.child_project_id_namespace)
                 & (path.children.local_id == pip1.child_project_local_id) )
        ).link(
            project,
            on=( (pip1.parent_project_id_namespace == project.id_namespace)
                 & (pip1.parent_project_local_id == project.local_id) ),
            join_type='right'
        )

        if use_root_projects:
            path = path.link(self.builder.CFDE.project_root)
        elif parent_project_RID is not None:
            pip2 = self.builder.CFDE.project_in_project.alias('pip2')
            parent = self.builder.CFDE.project.alias("parent")
            path = path.link(
                pip2,
                on=( (path.project.id_namespace == pip2.child_project_id_namespace)
                     & (path.project.local_id == pip2.child_project_local_id) )
            ).link(
                parent,
                on=( (path.pip2.parent_project_id_namespace == parent.id_namespace)
                     & (path.pip2.parent_project_local_id == parent.local_id) )
            ).filter(path.parent.RID == parent_project_RID)

        return path.groupby(
            path.project.RID,
        ).attributes(
            path.project.id_namespace,
            path.project.local_id,
            path.project.column_definitions['name'],
            path.project.abbreviation,
            path.project.description,
            CntD(path.children.RID).alias('num_subprojects'),
        )

    def list_datatypes(self):
        """Return list of data_type terms
        """
        return self.builder.CFDE.data_type.path.entities().fetch()
    
    def list_formats(self):
        """Return list of file format terms
        """
        return self.builder.CFDE.file_format.path.entities().fetch()

## ugly CLI wrapping...
def main():
    """Runs demo of catalog dashboard queries."""
    hostname = os.getenv('DERIVA_SERVERNAME', 'app-dev.nih-cfde.org')
    catalogid = os.getenv('DERIVA_CATALOGID', '4')
    db = DashboardQueryHelper(hostname, catalogid)
    db.run_demo()
    return 0

if __name__ == '__main__':
    exit(main())
