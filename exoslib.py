import sys
import json, re, os
import exsh
try:
    ElementTree
except NameError:
    try:
        import xml.etree.cElementTree as ElementTree
    except ImportError:
        import xml.etree.ElementTree as ElementTree



def cfg_areas():
    """
    Returns a list of config modules with non-default config
    Does not support user-created VRs.
    """

    cfg_modules = []
    config = exsh.clicmd('show config', capture=True)
    config = config.splitlines(True)
    moduleName = ''
    moduleStr = ''
    configExist = False   
    for line in config:
        if '#' not in line and line != '\n':
            moduleStr += line
            configExist = True
        elif configExist is True and '#' in line:
            cfg_modules.append(moduleName)
            moduleStr = line
            moduleName = ''
            configExist = False
        elif '#' in line:
            moduleStr += line
            configExist = False
            if '# Module ' in line:
                moduleName = line.replace('# Module ','')
                moduleName = moduleName.replace(' configuration.\n','')
                moduleName = moduleName.lower()
        elif configExist is True and line == '\n':
            moduleStr += line
        else:
            moduleStr = ''
    return cfg_modules

def change_vr(vr): 
    """
    This will change the VR context that the script is running in.

    Values for vr
    VR-Default: 2
    VR-Mgmt: 0                                                           
    # Any other number the number of your user created VR.
    """                                                   
    try:                                                           
        f = open('/proc/self/ns_id', 'w')                          
        f.write(vr+'\n')                                           
        f.close()                                                  
        return True                                                
    except:                                                        
        return False

def cmd2data(clicmd):
    """
    Runs an EXOS command and returns the output in json format
    """
    
    re_reply = re.compile(r'<reply>.+?</reply>', re.DOTALL)
    xmlout = exsh.clicmd(clicmd, capture=False, xml=True)
    data = []
    for reply in re.finditer(re_reply, xmlout):
        if reply:
            reply_xml = reply.group()
            root = ElementTree.fromstring(reply_xml)
            for message in root.iter('message'):
                for element in message:
                    mdata = {}
                    edata = {}
                    for e in element:
                        text = int(e.text) if e.text is not None and e.text.isdigit() else e.text
                        edata[e.tag] = text
                    mdata[element.tag] = edata
                    data.append(mdata)
    return data

def get_active_ports():
    active_list = []
    vlan_ports_info = json.loads(exsh.clicmd('debug cfgmgr show next vlan.show_ports_info port=None '
                                             'portList=*', capture=True, xml=False))
    for item in vlan_ports_info['data']:
        if item['linkState'] == '1':
            active_list.append(item['port'])

    return active_list


def get_all_ports():
    """Create and return a EXOS CLI friendly port list string containing all device ports

    Some show commands do not provide a "port all" option but allow for specifiying a port list. This method creates
    an "all" port list to be used with these CLI commands

    In the future this may be used to return the all port string as well as an active port list

    :return: str. -- EXOS CLI friendly port list containing all ports on device
    """
    vlan_ports_info = json.loads(exsh.clicmd('debug cfgmgr show next maximum-rows 1 vlan.show_ports_info port=None portList=*', capture=True, xml=False))
    all_ports = vlan_ports_info['data'][0]['portList']
    return all_ports

def get_port_vlans(port):
    vlanRslt = json.loads(exsh.clicmd('debug cfgmgr show next vlan.show_ports_info_detail_vlans formatted port={0} vlanIfInstance=None'.format(port), True))
    port_data = []
    for vlanRow in vlanRslt['data']:
        port_data.append({'VlanName' : str(vlanRow['vlanName']), 'VlanId' : str(vlanRow['vlanId']), 'tag' : str(vlanRow['tagStatus'])})
    return port_data

def get_platform():
        """Determine device platform type and return it

        Use python environment variables to determine the platform type and return it.

        Possible Platform Values:
        Summit
        SummitStack
        BD8800
        BDX8

        :return: string -- device platform type
        :raises: RuntimeError
        """
        exos_platform = os.environ.get('EXOS_PLATFORM_TYPE')
        # Check if platform is Summit
        if exos_platform == '1':
            # Check if stacking is enabled
            stack_mode = os.environ.get('EXOS_STACK_MODE')
            if stack_mode == '1':
                # Device is stack
                platform = 'SummitStack'
            else:
                # Device is standalone
                platform = 'Summit'
        # Check if platform is Chassis
        elif exos_platform == '2':
            chassis_type = os.environ.get('EXOS_SWITCH_PLATFORM')
            # Check if platform is Everest or Aspen
            if chassis_type == 'everest':
                platform = 'BDX8'
            else:
                # Assume device is Aspen
                platform = 'BD8800'
        else:
            raise RuntimeError('Unknown platform type: {0}'.format(exos_platform))
        return platform


def get_vlans():
    """
    Returns a list of all VLANs created on the switch
    """

    output = json.loads(exsh.clicmd('debug cfgmgr show next vlan.vlan', capture=True))
    output = output['data']
    vlans = []
    for item in output:
        vlans.append(item['name'])
    return set(vlans)

def get_vlan_ports(vlan):
    vlanportsRslt = json.loads(exsh.clicmd('debug cfgmgr show one vlan.vlanPort vlanName={0}'.format(vlan), True))

    return  ({'untagged' : str(vlanportsRslt['data'][0]['untaggedPorts']), 'tagged' : str(vlanportsRslt['data'][0]['taggedPorts'])})

def ip_stats():
    """
    replacement for global 'show ipstats' missing in EXOS 30.1 and above
    """

    retval = []
    for vlan in get_vlans():
        command = "show ipstats vlan {0}".format(vlan)
        out = cmd2data(command)
        if len(out) > 0:
            retval.append(out[0])
    return retval

def halDebugCongestion():
    """
    Returns CPU and fabric congestion for all switches in a stack.
	If the switch is a standalone it will report as slot 1.
    """

    stackRslt = json.loads(exsh.clicmd('debug cfgmgr show next hal.halDebugCongestion formatted', True))
    slot_data = []
    for slot in stackRslt['data']:
        slot_data.append({'Slot' : str(slot['slot']), 'cpu_cng' : str(slot['cpu_cng']), 'fabric_cng' : str(slot['fabric_cng'])})
    return slot_data

def is_port_active(port):
    port_status = json.loads(exsh.clicmd('debug cfgmgr show one vlan.show_ports_info formatted portList={0}'.format(port), capture=True))
    port_status = port_status['data'][0]['linkState']
    if port_status == '1':
        return True
    else:
        return False


def operational_slots():
    """Check slot status and return list of operational slots

    :return: list -- operational slots
    """
    if get_platform() == 'Summit':
        return ['1']
    op_slots = []
    dm_card_info = json.loads(exsh.clicmd('debug cfgmgr show next dm.card_info', capture=True, xml=False))
    dm_card_info = dm_card_info['data']
    for item in dm_card_info:
        if item['card_state_str'] == 'Operational' and item['slot'] not in op_slots:
            op_slots.append(item['slot'])
    return op_slots

def port_is_valid(port):
    port = port.replace(' ', '')
    port_check = json.loads(exsh.clicmd('debug cfgmgr show next maximum-rows 1 vlan.show_ports_info portList={0}'.format(port), capture=True, xml=False))
    if port_check['data'][0]['status'] == 'SUCCESS':
        return True
    else:
        return False

def yes_no_input(request, default=False):
    FMT_ERROR = 'ERROR: {0}'
    input = raw_input(request)
    if input in ('y','Y'):
        return True
    elif input in ('n','N'):
        return False
    elif input in ('') and default is not None:
        return default
    print FMT_ERROR.format('Invalid input.  Please enter \'y\' or \'n\'')
    yes_no_input(request, default)






 



