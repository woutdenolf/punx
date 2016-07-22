#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# :author:    Pete R. Jemian
# :email:     prjemian@gmail.com
# :copyright: (c) 2016, Pete R. Jemian
#
# Distributed under the terms of the Creative Commons Attribution 4.0 International Public License.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------

'''
validate NeXus NXDL and HDF5 data files

.. autosummary::
   
   ~validate_xml
   ~NxdlPattern
   ~CustomNxdlPattern
   ~Data_File_Validator

These are considerata for the validation of NeXus HDF5 data files.
Compare these validation steps with rules and documentation
in the NeXus manual and the XML Schema files (``nxdl.xsd`` and ``nxdlTypes.xsd``).
Checkboxes indicate which steps have been implemented in code below.

* [x] make a list of all address nodes in the file to be evaluated
* [x] attributes are also in this list
* [x] use a structure to hold results for each node

.. rubric:: File

#. [x] verify attributes
#. [x] verify file level as group using NX_class = NXroot
#. [ ] identify any objects at root level that are not in NXroot (which is OK)
#. [x] verify default plot identified

    #. [x] version 1
    #. [x] version 2
    #. [x] version 3
    #. [x] version 3+niac2014

.. rubric:: Groups

#. [x] compare name with pattern *validItemName*
#. [x] determine NX_class, if any
#. [x] verify NX_class in nxdl_dict
#. [ ] is name flexible?
#. [ ] What to do with NXDL symbol tables?
#. [ ] observe attributes: minOccurs maxOccurs
#. [ ] is deprecated?
#. [ ] special cases:

    #. [ ] NXentry
    #. [ ] NXsubentry
    #. [ ] NXdata
    #. [x] NXcollection

#. [ ] check for items defined by NX_class
#. [ ] check for items required by NX_class
#. [ ] check for items not defined by NX_class
#. [ ] observe NXDL setting: ignoreExtraGroups
#. [ ] observe NXDL setting: ignoreExtraFields
#. [ ] observe NXDL setting: ignoreExtraAttributes
#. [x] validate any attributes
#. [x] validate any links
#. [x] validate any fields

.. rubric:: Links

#. [x] compare name with pattern *validItemName*
#. [ ] is name flexible?
#. [x] is target attribute defined?
#. [x] is target address absolute?
#. [x] does target address exist?
#. [ ] construct NX classpath from target
#. [ ] compare NX classpath with NXDL specification

.. rubric:: Fields

#. [x] compare name with pattern
#. [ ] is name flexible?
#. [ ] observe attributes: minOccurs maxOccurs
#. [ ] is deprecated?
#. [x] is units attribute defined?
#. [x] check units are consistent against NXDL
#. [ ] check data shape against NXDL
#. [ ] check data type against NXDL
#. [x] check for attributes defined by NXDL
#. [ ] check AXISNAME_indices are each within signal data rank

.. rubric:: Attributes

#. [x] compare name with pattern
#. [ ] is deprecated?
#. [ ] check data type against NXDL
#. [ ] check nxdl.xsd for how to handle these attributes regarding finding.WARN

    #. [ ] restricts
    #. [ ] ignoreExtraGroups
    #. [ ] ignoreExtraFields
    #. [ ] ignoreExtraAttributes

'''

import collections
import h5py
import lxml.etree
import numpy
import os
import re

import __init__
import cache
import finding
import h5structure
import nxdlstructure

# TODO: issue #14: http://download.nexusformat.org/doc/html/search.html?q=warning&check_keywords=yes&area=default

__url__ = 'http://punx.readthedocs.org/en/latest/validate.html'

# for each NeXus data type, make a list of acceptable Python data types
# Is there a better way to define these?  Using nxdlTypes.xsd?
NXDL_DATA_TYPES = {
    'NX_CHAR': (str, unicode, numpy.string_, numpy.ndarray),
    'NX_INT':  (int, numpy.int, numpy.int8, numpy.int16, numpy.int32, numpy.int64),
    'NX_FLOAT':  (float, ),
    'NX_BINARY': (None, ),     # #FIXME: issue #21
    'NX_BOOLEAN': (None, ),     # FIXME: issue #21
}
# definitions dependent on other definitions
# (can add the lists together as needed)
NXDL_DATA_TYPES['NX_UINT']   = NXDL_DATA_TYPES['NX_INT']
NXDL_DATA_TYPES['NX_POSINT'] = NXDL_DATA_TYPES['NX_INT']
NXDL_DATA_TYPES['NX_NUMBER'] = NXDL_DATA_TYPES['NX_INT'] + NXDL_DATA_TYPES['NX_FLOAT']
NXDL_DATA_TYPES['ISO8601']   = NXDL_DATA_TYPES['NX_CHAR']
NXDL_DATA_TYPES['NX_DATE_TIME']   = NXDL_DATA_TYPES['NX_CHAR']


def validate_xml(xml_file_name):
    '''
    validate an NXDL XML file against an XML Schema file

    :param str xml_file_name: name of XML file
    '''
    xml_tree = lxml.etree.parse(xml_file_name)
    xsd = cache.get_XML_Schema()
    return xsd.assertValid(xml_tree)


class NxdlPattern(object):
    '''
    common regular expression pattern for validation
    
    :param obj parent: instance of :class:`Data_File_Validator`
    :param str pname: pattern identifying name
    :param str xpath_str: XPath search string, expect list of length = 1
    '''
    
    def __init__(self, parent, pname, xpath_str):
        self.name = pname
        self.xpath_str = xpath_str

        r = parent.nxdl_xsd.xpath(xpath_str, namespaces=parent.ns)

        if r is None or len(r) != 1:
            msg = 'could not read *' + pname + '* from *nxdl.xsd*'
            raise ValueError(msg)

        self.regexp_pattern_str = r[0].attrib.get('value', None)
        self.re_obj = re.compile('^' + self.regexp_pattern_str + '$')
    
    def match(self, text):
        '''regular expression search'''
        return self.re_obj.match(text)


class CustomNxdlPattern(NxdlPattern):
    '''
    custom regular expression pattern for validation
    
    :param obj parent: instance of :class:`Data_File_Validator`
    :param str pname: pattern identifying name
    :param str regexp_pattern_str: regular expression to match
    '''
    
    def __init__(self, parent, pname, regexp_pattern_str):
        self.name = pname
        self.xpath_str = None

        self.regexp_pattern_str = regexp_pattern_str
        self.re_obj = re.compile('^' + self.regexp_pattern_str + '$')
    
    def match(self, text):
        '''regular expression search'''
        return self.re_obj.match(text)


class Data_File_Validator(object):
    '''
    manage the validation of a NeXus HDF5 data file
    '''
    
    def __init__(self, fname):
        if not os.path.exists(fname):
            raise __init__.FileNotFound(fname)
        self.fname = fname

        self.findings = []      # list of Finding() instances
        self.addresses = collections.OrderedDict()     # dictionary of all HDF5 address nodes in the data file

        self.ns = cache.NX_DICT
        self.nxdl_xsd = cache.get_nxdl_xsd()
        nxdlTypes_xsd_file = cache.abs_NXDL_filename(cache.NXDL_TYPES_SCHEMA_FILE)
        self.nxdlTypes_xsd = lxml.etree.parse(nxdlTypes_xsd_file)
        self.nxdl_rules = nxdlstructure.get_nxdl_rules()

        self.nxdl_dict = nxdlstructure.get_NXDL_specifications()
        try:
            self.h5 = h5py.File(fname, 'r')
        except IOError:
            raise __init__.HDF5_Open_Error(fname)
        self._init_patterns()
    
    def _init_patterns(self):
        self.patterns = {}
        for item in ('validItemName', 'validNXClassName', 
                     'validTargetName'):
            xps = '//*[@name="' # XPath String query
            xps += item
            xps += '"]/xs:restriction/xs:pattern'
            self.patterns[item] = NxdlPattern(self, item, xps)

        # strict match: [a-z_][a-z\d_]*
        # flexible match: [A-Za-z_][\w_]*  but gets finding.WARN per manual
        # advisory changed to finding.NOTE
        p = CustomNxdlPattern(self, 'validItemName-strict', r'[a-z_][a-z0-9_]*')
        self.patterns[p.name] = p
        self.__unique_findings__ = {}
        
    def validate(self):
        '''
        start the validation process from the file root
        '''
        self.validate_HDF5_group(self.h5)
        self.validate_default_plot()
        
    def validate_HDF5_group(self, group):
        '''
        review the HDF5 group: group

        :param obj group: instance of h5py.File of h5py.Group
        
        Verify that items presented in data file are valid.
        '''
        nx_class_name = self.get_hdf5_attribute(group, 'NX_class', report=True)
        if nx_class_name is None:
            if isinstance(group, h5py.File):
                nx_class_name = 'NXroot'
                msg = 'file root: NXroot'
                self.new_finding('@NX_class assumed', group.name, finding.OK, msg)
            else:
                self.validate_item_name(group.name)
                msg = 'no @NX_class attribute, not a NeXus group'
                self.new_finding('@NX_class exists', group.name, finding.NOTE, msg)
                return  # evaluate any further?
        else:
            self.validate_item_name(group.name)

            aname = group.name + '@NX_class'
            t = nx_class_name in self.nxdl_dict
            f = finding.TF_RESULT[t]
            msg = nx_class_name + {True: ' is ', False: ' is not '}[t] + 'known'
            self.new_finding('@NX_class known', aname, f, msg)
        
        nx_class_object = self.nxdl_dict.get(nx_class_name)
        if nx_class_object is not None:
            for item in 'ignoreExtraAttributes ignoreExtraFields ignoreExtraGroups'.split():
                if nx_class_object.attributes['defaults'][item]:
                    msg = 'True'
                    self.new_finding(nx_class_name+'@'+item, group.name, finding.TODO, msg)
        
        # NeXus special case
        if nx_class_name == 'NXcollection':
            msg = 'NXcollection content will not be validated'
            self.new_finding('NXcollection group', group.name, finding.OK, msg)
            return
        
        for k in group.attrs.keys():   # review the group's attributes
            if k not in ('NX_class',):
                aname = group.name + '@' + k
                self.validate_item_name(aname)

        for child_name in group:           # review the group's children
            child = group[child_name]
            if h5structure.isNeXusLink(child):
                self.validate_NeXus_link(child, group)
            elif h5structure.isHdf5Group(child):
                self.validate_HDF5_group(child)
            elif h5structure.isHdf5Dataset(child):
                self.validate_HDF5_dataset(child, group)
            else:
                msg = 'unexpected: ' + child.name
                raise ValueError(msg)
        
        self.validate_NXDL_specification(group, nx_class_name)
        if nx_class_name in ('NXsubentry', 'NXentry') and 'definition' in group:
            # application definition masquerading as NXentry or NXsubentry
            app_def_name = group['definition'][0]
            # TODO: need special handling for application definitions
            self.validate_NXDL_specification(group, app_def_name)
   
    def validate_HDF5_dataset(self, dataset, group):
        '''
        review the HDF5 dataset: dataset

        :param obj dataset: instance of h5py.Dataset
        :param obj group: instance of h5py.Group or h5py.File, needed to check against NXDL
        '''
        self.validate_item_name(dataset.name)
        field_rules = self.nxdl_rules.nxdl.children['field']
        nx_class_name = self.get_hdf5_attribute(group, 'NX_class')
        nx_class_object = self.nxdl_dict.get(nx_class_name)

        for k in dataset.attrs.keys():   # review the dataset's attributes
            aname = dataset.name + '@' + k
            self.validate_item_name(aname)
            v = self.get_hdf5_attribute(dataset, k, report=True)
            if k in field_rules.attrs:
                rules = field_rules.attrs[k]
                if len(rules.enum) > 0:
                    t = v in rules.enum
                    f = {True: finding.OK, False: finding.WARN}[t]
                    msg = 'value=' + v
                    if t:
                        msg += ' :recognized'
                    else:
                        msg += ' : expected one of these: ' + '|'.join(rules.enum)
                    self.new_finding('enumeration: @' + k, aname, f, msg)
                pass    # TODO: other validations?
            else:
                if k not in ('target',):    # could be one end of a link
                    if nx_class_object is not None:
                        if not nx_class_object.attributes['defaults']['ignoreExtraAttributes']:
                            msg = 'attribute not defined in NXDL'
                            self.new_finding(nx_class_name + '@' + k, aname, finding.NOTE, msg)
        
        # check the units of numerical fields
        if dataset.dtype in NXDL_DATA_TYPES['NX_NUMBER']:
            title = 'field@units'
            units = self.get_hdf5_attribute(dataset, 'units', report=True)
            t = units is not None
            f = {True: finding.OK, False: finding.NOTE}[t]
            msg = {True: 'exists', False: 'does not exist'}[t]
            if t:
                t = len(units) > 0
                f = {True: finding.OK, False: finding.NOTE}[t]
                msg = {True: 'value: ' + units, False: 'has no value'}[t]
            self.new_finding(title, dataset.name + '@units', f, msg)
            
            # TODO: issue #13: check field dimensions against "rank" attribute 
            shape = dataset.shape
            __ = None   # used as a NOP breakpoint after previous definition

        # check the type of this field
        # https://github.com/prjemian/punx/blob/b595fdf9910dbab113cfe8febbb37e6c5b48d74f/src/punx/validate.py#L761

        # review the dataset's content
        nx_class_name = self.get_hdf5_attribute(group, 'NX_class')
        if nx_class_name in self.nxdl_dict:
            nx_class = self.nxdl_dict[nx_class_name]
            rules = nx_class.fields.get(dataset.name.split('/')[-1])
            if rules is not None:
                if len(rules.enum) > 0:
                    pass    # TODO:
                # TODO: check rules.attributes['defaults'] for type, minOccurs, nameType
                nx_type = rules.attributes['defaults']['type']
                minO = rules.attributes['defaults']['minOccurs']
                maxO = rules.attributes['defaults']['maxOccurs']
                specified = rules.attributes['defaults']['nameType'] == 'specified'
                __ = None
                        
    def validate_NeXus_link(self, link, group):
        '''
        review the NeXus link: link
        
        :param obj link: instance of h5py.Group or h5py.Dataset
        :param obj group: instance of h5py.Group, needed to check against NXDL
        '''
        self.validate_item_name(link.name)

        target = self.get_hdf5_attribute(link, 'target', report=True)
        if target is not None:
            aname = link.name + '@target'
            target_exists = target in self.h5
            f = finding.TF_RESULT[target_exists]
            msg = {True: target, False: 'does not exist'}[target_exists]
            self.new_finding('link target exists', aname, f, msg)
        else:
            self.new_finding('link', link.name, finding.ERROR, 'no target')
        
    def validate_NXDL_specification(self, group, nx_class_name):
        '''
        validate the group with the NXDL specification

        :param obj group: instance of h5py.Group or h5py.File
        :param str nx_class_name: name of a NeXus NXDL class
        
        Verify that items specified in NXDL file are present in the data file.
        '''
        nx_class_object = self.nxdl_dict.get(nx_class_name)
        if nx_class_object is None:
            return

        # TODO: review with NXDL specification: nx_class_object
        msg = 'validate with ' + nx_class_name + ' specification (incomplete)'
        self.new_finding('NXDL review: '+nx_class_name, group.name, finding.TODO, msg)

        # validate provided, required, and optional fields
        for field_name, rules in nx_class_object.fields.items():
            nx_type = NXDL_DATA_TYPES[rules.attributes['defaults']['type']]

            minO = rules.attributes['defaults']['minOccurs']
            maxO = rules.attributes['defaults']['maxOccurs']
            required_name = rules.attributes['defaults']['nameType'] == 'specified'
            target_exists = field_name in group
            if int(minO) > 0 and required_name:
                f = {True: finding.OK, False: finding.WARN}[target_exists]
                finding.TF_RESULT[target_exists]
                m = {True: '', False: ' not'}[target_exists] + ' found'
                nm = group.name + '/' + field_name
                self.new_finding(nx_class_name+' required field', nm, f, m)
                # TODO:

        # validate provided, required, and optional groups (recursive as directed)
        for group_name, rules in nx_class_object.groups.items():
            minO = rules.attributes['defaults']['minOccurs']
            maxO = rules.attributes['defaults']['maxOccurs']
            if int(minO) > 0:
                if rules.attributes['defaults']['name'] is not None:
                    nm = group.name + '/' + group_name
                    t = group_name in group
                    f = {True: finding.OK, False: finding.WARN}[t]
                    m = rules.NX_class + {True: ' found', False: ' not found'}[t]
                    self.new_finding(nx_class_name+' required group', nm, f, m)
                else:
                    matches = [node for node in group.values() if h5structure.isNeXusGroup(node, rules.NX_class)]
                    if len(matches) < int(minO):
                        nm = group.name
                        m = 'must have at least ' + str(minO) + ' group: ' + rules.NX_class 
                        f = finding.WARN
                        self.new_finding(nx_class_name+' required group', nm, f, m)
            # TODO: what else?
                       

    def validate_item_name(self, h5_addr):
        '''
        validate *h5_addr* using *validItemName* regular expression
        
        This is used for the names of groups, fields, links, and attributes.
        
        :param str h5_addr: full HDF5 address of item, for reference only,
            for attributes, use an @ symbol, such as these examples:
            
            =============================    ============
            *h5_addr*                        *short_name*
            =============================    ============
            ``/entry/user``                  ``user``
            ``/entry/data01/data``           ``data``
            ``/entry/data01/data@signal``    ``signal``
            =============================    ============

        This method will separate out the last part of the name for validation.  
        Then, it is tested against the strict or relaxed regular expressions for 
        a valid item name.  The finding for each name is classified by the
        next table:
        
        =====  =======  =======  ================================================================
        order  finding  match    description
        =====  =======  =======  ================================================================
        1      OK       strict   matches most stringent NeXus specification
        2      NOTE     relaxed  matches NeXus specification that is most generally accepted
        3      ERROR    UTF8     specific to strings with UnicodeDecodeError (see issue #37)
        4      WARN     HDF5     acceptable to HDF5 but not NeXus
        =====  =======  =======  ================================================================
        
        :see: http://download.nexusformat.org/doc/html/datarules.html?highlight=regular%20expression
        '''
        key_relaxed = 'validItemName'
        key_strict = 'validItemName-strict'

        # h5_addr = obj.name
        short_name = h5_addr.split('/')[-1].split('@')[-1]
        if short_name == 'NX_class':
            # special case
            self.new_finding('NeXus internal attribute', 
                             h5_addr, 
                             finding.OK, 
                             'marks this HDF5 group as NeXus group')
            return
        
        # strict match: [a-z_][a-z\d_]*
        # flexible match: [A-Za-z_][\w_]*  but gets finding.WARN per manual

        p = self.patterns[key_strict]
        m = p.match(short_name)
        if m is not None and m.string == short_name:
            f = finding.OK
            key = key_strict
            msg =  'strict re: ' + p.regexp_pattern_str
        else:
            p = self.patterns[key_relaxed]
            m = p.match(short_name)
            if m is not None and m.string == short_name:
                f = finding.NOTE
                key = key_relaxed
                msg =  'relaxed re: ' + p.regexp_pattern_str
            else:
                # test if string rendering raises UnicodeDecodeError
                key = 'validItemName'
                msg = 'valid HDF5 item name, not valid with NeXus'
                try:    # to raise the exception
                    _test = '%s' % str(m)
                    f = finding.WARN
                except UnicodeDecodeError, _exc:
                    f = finding.ERROR

        self.new_finding(key, h5_addr, f, msg)
    
    def validate_default_plot(self):
        '''
        check that data file defines the default plottable data
        
        :see: http://download.nexusformat.org/doc/html/datarules.html#find-the-plottable-data
        '''
        candidates = self.identify_default_plot_candidates()
        if self.default_plot_addr_v3(candidates['v3']) is not None:
            return
        elif self.default_plot_addr_v2(candidates['v2']) is not None:
            return
        elif self.default_plot_addr_v1(candidates['v1']) is not None:
            return
        
        m = 'no default plot: not a NeXus file'
        self.new_finding('NeXus default plot', '/NXentry/NXdata/field', finding.ERROR, m)
    
    def identify_default_plot_candidates(self):
        '''
        find the HDF5 addresses that might provide the default plottable data
        
        :see: http://download.nexusformat.org/doc/html/datarules.html#find-the-plottable-data
        :see: http://download.nexusformat.org/doc/html/preface.html?highlight=class%20path#class-path-specification
        
        There are different methods to identify the default data to be plotted.
        These can be distinguished by differences in the NeXus class path
        (the sequence of NeXus classes and other elements that describe an object in
        a NeXus HDF5 data file).  As used here, the text ``field`` is used
        instead of the name of the field (as shown in the NeXus manual) but the name of the
        attribute is given.
        
        ===========   =======================================
        version       NeXus classpath signature
        ===========   =======================================
        v3            /NXentry/NXdata@signal
        v3+niac2014   /@default/NXentry@default/NXdata@signal
        v2            /NXentry/NXdata/field@signal
        v1            /NXentry/NXdata/field@signal
        ===========   =======================================
        
        Versions *v1* and *v2* differ in their use of other attributes
        such as *axes* (v2) versus *axis* (v1) and *primary* (v1).
        with other attributes such as */NXentry/NXdata/field2@primary*.
        Since these other attributes are not always present, or
        might be used to indicate alternatives, a test for *v1*
        can fail due to both false negatives and false positives.
        '''
        # prepare dictionaries of candidates for the default plot
        candidates = dict(v1 = {}, v2 = {}, v3 = {})
        for node_name in self.h5:
            node = self.h5[node_name]
            if h5structure.isNeXusGroup(node, 'NXentry'):
                for subnode_name in node:
                    subnode = node[subnode_name]
                    if h5structure.isNeXusGroup(subnode, 'NXdata'):
                        if subnode.attrs.get('signal') is not None:
                            k = subnode.name + '@signal'
                            candidates['v3'][k] = '/NXentry/NXdata@signal'
                        for ss_node_name in subnode:
                            ss_node = subnode[ss_node_name]
                            if not h5structure.isNeXusDataset(ss_node):
                                continue
                            if ss_node.attrs.get('signal') is not None:
                                k = ss_node.name + '@signal'
                                candidates['v2'][k] = '/NXentry/NXdata/field@signal'
                                candidates['v1'][k] = '/NXentry/NXdata/field@signal'
        return candidates

    def default_plot_addr_v1(self, group_dict):
        '''
        return the HDF5 address of the v1 default plottable data or None
        
        :see: http://download.nexusformat.org/doc/html/datarules.html#version-1
        '''
        default_plot_addr = []
        for primary_field_addr, nx_classpath in group_dict.items():
            title = 'NXdata group default plot v1'
            # need the NXdata group of this field
            primary = self.h5[primary_field_addr.split('@')[0]]
            nxdata_addr = '/'.join(primary.name.split('/')[:-1])
            nxdata = self.h5[nxdata_addr]
            signal_field_list = []
            for field_name in nxdata:
                field = nxdata[field_name]
                if h5structure.isNeXusDataset(field):
                    signal = self.get_hdf5_attribute(field, 'signal', report=True)
                    if signal is None:
                        continue
                    elif signal in (1, '1'):
                        signal_field_list.append(field)
                    else:
                        m = 'expected @signal=1, found: ' + signal
                        addr = field.name + '@signal'
                        self.new_finding(title, addr, finding.ERROR, m)
                        continue
                # TODO: @axis, @primary, and dimension scales
                # TODO: signal and dimension scales data shape

            if len(signal_field_list) == 1:
                m = 'NXdata group default plot using v1'
                self.new_finding(title, signal_field_list[0], finding.OK, m)
                default_plot_addr.append(signal_field_list[0])
            elif len(signal_field_list) == 0:
                m = 'NXdata group does not define a default plot using v1'
                self.new_finding(title, nxdata_addr, finding.WARN, m)
            else:
                m = 'NXdata group defines more than one default plot using v1'
                self.new_finding(title, nxdata_addr, finding.NOTE, m)
        
        cp = 'NXdata/field@signal'
        title = 'NeXus default plot v1'
        if len(default_plot_addr) == 1:
            m = 'NeXus data file default plot defined'
            self.new_finding(title, default_plot_addr[0], finding.OK, m)
            return default_plot_addr[0]
        elif len(default_plot_addr) == 0:
            m = 'NeXus data file does not define a default plot using v1'
            #self.new_finding(title, cp, finding.WARN, m)
        else:
            m = 'NeXus data file defines more than one default plot using v1'
            self.new_finding(title, cp, finding.WARN, m)
            return default_plot_addr
    
    def default_plot_addr_v2(self, group_dict):
        '''
        return the HDF5 address of the v2 default plottable data or None
        
        :see: http://download.nexusformat.org/doc/html/datarules.html#version-2
        '''
        default_plot_addr = []
        for h5_addr, nx_classpath in group_dict.items():
            title = 'NeXus default plot v2'
            field = self.h5[h5_addr.split('@')[0]]
            signal = self.get_hdf5_attribute(field, 'signal', report=True)
            if signal in (1, '1'):
                m = nx_classpath + ' = 1'
                self.new_finding(title, field.name, finding.OK, m)
                default_plot_addr.append(field.name)
            else:
                m = 'expected @signal=1, found: ' + signal
                self.new_finding(title, h5_addr, finding.ERROR, m)
            # TODO: @axes, @AXISNAME_indices, and dimension scales    (see issue #41)
            # TODO: signal and dimension scales data shape

        cp = 'NXdata/field@signal'
        title = 'NeXus default plot v2'
        if len(default_plot_addr) == 1:
            m = 'NeXus data file default plot defined using v2'
            self.new_finding(title, default_plot_addr[0], finding.OK, m)
            return default_plot_addr[0]
        elif len(default_plot_addr) == 0:
            m = 'NeXus data file does not define a default plot using v2'
            #self.new_finding(title, cp, finding.WARN, m)
        else:
            m = 'NeXus data file defines more than one default plot using v2'
            self.new_finding(title, cp, finding.NOTE, m)
            return default_plot_addr
    
    def default_plot_addr_v3(self, group_dict):
        '''
        return the HDF5 address of the v3 default plottable data or None
        
        :see: http://download.nexusformat.org/doc/html/datarules.html#version-3
        '''
        default_plot_addr = []
        for h5_addr, nx_classpath in group_dict.items():
            title = 'NXdata group default plot v3'
            nxdata = self.h5[h5_addr.split('@')[0]]
            signal_name = self.get_hdf5_attribute(nxdata, 'signal', report=True)
            if signal_name not in nxdata:
                m = 'signal field not found: ' + signal_name
                self.new_finding(title, nx_classpath, finding.ERROR, m)
                continue
            #m = 'signal data: ' + signal_name
            # m = nx_classpath + ' = ' + signal_name
            m = 'NXdata@signal = ' + signal_name
            addr = nxdata.name + '/' + signal_name
            self.new_finding(title, addr, finding.OK, m)
            default_plot_addr.append(addr)
            # TODO: @axes and dimension scales    (see issue #41)
            # TODO: signal and dimension scales data shape

        cp = 'NXdata@signal'
        title = 'NeXus default plot v3'
        if len(default_plot_addr) == 1:
            m = 'NeXus data file default plot: /NXentry/NXdata@signal'
            self.new_finding(title, default_plot_addr[0], finding.OK, m)
            return default_plot_addr[0]
        elif len(default_plot_addr) == 0:
            m = 'NeXus data file does not define a default plot using v3'
            # self.new_finding(title, cp, finding.WARN, m)
        else:
            # use NIAC2014 terms to find unique address
            unique_list = self.default_plot_addr_v3_niac2014(default_plot_addr)
            if len(unique_list) == 1:
                m = 'NeXus data file default plot defined using v3+niac2014'
                self.new_finding(title, unique_list[0], finding.OK, m)
                return unique_list[0]
            else:
                m = 'NeXus data file defines more than one default plot'
                self.new_finding(title, cp, finding.NOTE, m)
                return default_plot_addr
    
    def default_plot_addr_v3_niac2014(self, address_list):
        '''
        return a list of default plottable data as directed by @default attributes
        
        :param [str] address_list: list of absolute HDF5 addresses with v3 default plottable data
        
        Each address fits this NeXus class path: /NXentry/NXdata/field  
        '''
        unique_list = []
        for k in address_list:
            nxentry_name = k.split('/')[1]
            root_default = self.get_hdf5_attribute(self.h5, 'default', nxentry_name)
            if root_default == nxentry_name:
                nxentry = self.h5[nxentry_name]
                nxdata_name = k.split('/')[2]
                nxentry_default = self.get_hdf5_attribute(nxentry, 'default', nxdata_name)
                if nxentry_default == nxdata_name:
                    unique_list.append(k)
        return unique_list

    def get_hdf5_attribute(self, obj, attribute, default=None, report=False):
        '''
        HDF5 attribute strings might be coded in several ways
        
        :param obj obj: instance of h5py.File, h5py.Group, or h5py.Dataset
        :param str attribute: name of requested attribute
        :param obj default: value if attribute not found (usually str)
        :param bool report: check & report if value is a variable length string (actually an ndarray)
        '''
        a = obj.attrs.get(attribute, default)
        if isinstance(a, numpy.ndarray):
            if report:
                gname = obj.name + '@' + attribute
                msg = '[variable length string]: ' + str(a)
                self.new_finding('attribute data type', gname, finding.NOTE, msg)
            a = a[0]
        return a

    def reconstruct_classpath(self, h5_address, *args, **kwargs):
        '''
        build the classpath from the h5_address
        '''
        path = h5_address.lstrip('/').split('@')[0]
        if len(path) == 0:
            return
 
        # reconstruct the NeXus classpath
        cp = ''     # classpath to be built
        hp = ''     # HDF5 address to be built
        for item in path.split('/'):
            hp += '/' + item
            if hp in self.h5:
                if h5structure.isHdf5Dataset(self.h5[hp]):
                    cp += '/field'
                else:
                    obj = self.h5[hp]
                    nx_class = self.get_hdf5_attribute(obj, 'NX_class', '-')
                    cp += '/' + nx_class
        if '@' in h5_address:
            cp += '@' + h5_address.split('@')[-1]
         
        return cp

    def new_finding(self, test_name, h5_address, status, comment):
        '''
        accumulate a list of findings
        
        :param str test_name: brief name of this test
        :param str h5_address: HDF5 address
        :param obj status: instance of finding.ValidationResultStatus,
                should be the same text as other instances of this test
        :param str comment: free-form explanation
        '''
        addr = str(h5_address)
        unique_key = addr + ':' + test_name
        if unique_key in self.__unique_findings__:
            # ensure that each test is only recorded once
            return
        f = finding.Finding(test_name, addr, status, comment)
        self.findings.append(f)
        self.__unique_findings__[unique_key] = f
        if addr not in self.addresses:
            # accumulate a dictionary of HDF5 object addresses
            self.addresses[addr] = finding.CheckupResults(addr)
            self.addresses[addr].classpath = self.reconstruct_classpath(addr)
        self.addresses[addr].findings.append(f)
    
    def report_findings(self, statuses=()):
        '''
        make a table of the validation findings
        
        :param statuses: List (or tuple) of finding statuses to be shown.
            Several lists have been pre-defined for convenience:

            :data:`finding.SHOW_ALL`        ``(OK, NOTE, WARN, ERROR, TODO, UNUSED, COMMENT)``
            :data:`finding.SHOW_NOT_OK`     ``(ERROR, WARN)``
            :data:`finding.SHOW_ERRORS`     ``(WARN, ERROR, TODO, UNUSED)``
            
            See :mod:`finding` for details.

        '''
        import pyRestTable

        t = pyRestTable.Table()
        t.labels = 'address validation status comment(s)'.split()
        for f in self.findings:
            if f.status in statuses:
                t.rows.append((f.h5_address, f.test_name, f.status, f.comment))
        return t.reST()
    
    def report_findings_summary(self):
        '''
        make a summary table of the validation findings (count how many of each status)
        '''
        import pyRestTable

        # count each category
        summary = collections.OrderedDict()
        for k in finding.VALID_STATUS_LIST:
            summary[str(k.key)] = 0
        xref = {str(k): k for k in finding.VALID_STATUS_LIST}
        for f in self.findings:
            summary[str(f.status)] += 1

        t = pyRestTable.Table()
        t.labels = 'status count description'.split()
        for k, v in summary.items():
                t.rows.append((k, v, xref[k].description))
        t.rows.append(('--', '--', '--'))
        t.rows.append(('TOTAL', len(self.findings), '--'))
        return t.reST()
    
    def report_classpath(self):
        import pyRestTable
        t = pyRestTable.Table()
        t.labels = 'HDF5-address  NeXus-classpath'.split()
        for k, v in self.addresses.items():
            t.rows.append((k, v.classpath))
        return t.reST()


if __name__ == '__main__':
    print "Start this module using:  python main.py validate ..."
    exit(0)
