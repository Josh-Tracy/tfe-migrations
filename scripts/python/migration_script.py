__version__ = "1.0.0"
__author__ = "Noah Eldreth"

from asyncio.log import logger
import os
import json
import time
import ssl
import logging
import base64
import hashlib
import argparse
from typing import Dict
import pandas as PD
from urllib import request
from terrasnek.api import TFC
from terrasnek.exceptions import *

# Authenticate with Owners Token to TFE/TFC Terraform Organization
TFE_SOURCE_TOKEN = os.getenv("TFE_SOURCE_TOKEN", "")
# Terraform Source URL
TFE_SOURCE_URL = os.getenv("TFE_SOURCE_URL", "") 
# Terraform Source Organization
TFE_SOURCE_ORG = os.getenv("TFE_SOURCE_ORG", "") 
# Verify SSL
TFE_SOURCE_VERIFY = os.getenv("TFE_SOURCE_VERIFY", False)
# VCS Providers' ot-* token(s) in Terraform Source
TFE_SOURCE_VCS = {
    "devops": "",
    "github": ""
}
# Source of module repositories if not specified by API response
TFE_SOURCE_DEFAULT_MODULE_VCS_PROVIDER = "devops"

# Authenticate with Owners Token to TFE/TFC Terraform Organization
TFC_TARGET_TOKEN = os.getenv("TFC_TARGET_TOKEN", "")
# Terraform Target URL
TFC_TARGET_URL = os.getenv("TFC_TARGET_URL", "") 
# Terraform Target Organization
TFC_TARGET_ORG = os.getenv("TFC_TARGET_ORG", "") 
# Verify SSL
TFC_TARGET_VERIFY  = os.getenv("TFC_TARGET_VERIFY", False)
# VCS Providers' ot-* token(s) in Terraform Target
TFC_TARGET_VCS = {
    "devops": "",
    "github": ""
}
# Variable Sets applied to Workspaces to provide data applicable to multiple workspaces
# Context: Workspace naming convention included either 'AWS' or 'ONPREM'
TFC_TARGET_VAR_SETS = {
    "aws": "",
    "onprem": ""
}

# Workspace Var Keys that will be deprecated by new variable sets in TFC Target
# Context: Workspace Variables that were associated per Workspace in source that we had included in variable sets
# Add variable keys to list
IGNORED_VARIABLE_KEYS = []

# Workspace Var Key Pairs that will need to be overwritten due to sensitivity
OVERWRITE_VARIABLE_KEY_PAIRS = {}

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', dest="debug", action="store_true", \
        help="If set, run the logger in debug mode.")        

    # Migrate Teams
    parser.add_argument('--migrate-teams', dest="migrate_teams", action="store_true", \
        help="Migrate Source Teams to TFC Target")

    # Migrate Workspaces
    parser.add_argument('--migrate-workspaces', dest="migrate_workspaces", action="store_true", \
        help="Migrate Source Workspaces to TFC Target")

    # Filepath for Workspace Variables
    parser.add_argument('--var-file-path', dest="var_file_path", default="./variables.csv", \
        help="Path to the Workspace Variables JSON file. Defaults to `./variables.csv`.")
    
    # Migrate Workspace Variables
    parser.add_argument('--create-workspace-vars', dest="create_workspace_vars", action="store_true", \
        help="Create all Workspace Variables in TFC Target")

    # Delete Workspace Variables
    parser.add_argument('--delete-workspace-vars', dest="delete_workspace_vars", action="store_true", \
        help="Delete all Workspace Variables from TFC Target")

    # Output Filepath for Source Workspace Variables
    parser.add_argument('--output-file-path', dest="output_file_path", default="./variables.csv", \
        help="Target path for CSV output. Defaults to `./variables.csv`.")

    # Create *.csv file for Source Workspace Variables
    parser.add_argument('--create-workspace-vars-csv', dest="create_workspace_vars_csv", action="store_true", \
        help="Create a CSV Spreadsheet for Source Workspace Variables")

    # Workspace Execution mode: local, remote, agent
    parser.add_argument('--execution-mode', dest="execution_mode", default="agent", \
        help="Execution mode for target workspaces. Defaults to `agent`.")

    # Workspace identifier: onprem, aws
    parser.add_argument('--workspace-identifier', dest="workspace_identifier", default="onprem", \
        help="Namespace identifier for target workspaces. Defaults to `onprem`.")

    # Update Workspace Execution Mode
    parser.add_argument('--update-workspace-execution', dest="update_workspace_execution", action="store_true", \
        help="Update Workspace Execution Mode for TFC Target")

    # Update Workspace Variable Set Associations
    parser.add_argument('--update-workspace-varsets', dest="update_workspace_varsets", action="store_true", \
        help="Update Workspace Variable Sets for TFC Target")

    # Migrate State files
    parser.add_argument('--migrate-current-state', dest="migrate_current_state", action="store_true", \
        help="Add Source Current State Version to Target Workspaces")

    # Migrate Registry Modules
    parser.add_argument('--migrate-registry-modules', dest="migrate_registry_modules", action="store_true", \
        help="Migrate Registry Module and version into TFC Target")

    args = parser.parse_args()

    return args

def create_source_variable_spreadsheet(source, filepath):
    workspaces = source.workspaces.list_all()['data']
    data = []
    for workspace in workspaces:
        logging.info(f"Acquring data for workspace: {workspace['attributes']['name']}...")
        workspace_vars = source.workspace_vars.list(workspace['id'])['data']
        for workspace_var in workspace_vars:
            logging.info(f"Reading information for variable: {workspace_var['attributes']['key']}...")
            if workspace_var['attributes']['key'] not in IGNORED_VARIABLE_KEYS:
                variable = {
                    "workspace_name": workspace['attributes']['name'],
                    "workspace_id": workspace['id'],
                    "variable_id": workspace_var['id'],
                    "variable_key": workspace_var['attributes']['key'],
                    "variable_value": workspace_var['attributes']['value'],
                    "variable_description": workspace_var['attributes']['description'],
                    "variable_category": workspace_var['attributes']['category'],
                    "variable_hcl": workspace_var['attributes']['hcl'],
                    "variable_sensitive": workspace_var['attributes']['sensitive']
                }
                if workspace_var['attributes']['key'] in OVERWRITE_VARIABLE_KEY_PAIRS:
                    variable['variable_value'] = OVERWRITE_VARIABLE_KEY_PAIRS[workspace_var['attributes']['key']]
                data.append(variable)

    PD.DataFrame(data).to_csv(filepath, index=False)

def deploy_target_workspace_variables(target, filepath):
    data = PD.read_csv(filepath).to_dict('records')
    total = len(data)
    for sensitive_variable in data:
        logging.info(f"({data.index(sensitive_variable) + 1}/{total}): Adding Workspace Variable '{sensitive_variable['variable_key']}' for workspace: {sensitive_variable['workspace_name']}...")

        workspace_variables = target.vars.list(sensitive_variable['workspace_name'])['data']
        workspace_variable_exists = False
        for workspace_variable in workspace_variables:
            if workspace_variable['attributes']['key'] == sensitive_variable['variable_key']:
                workspace_variable_exists = True
                break
        if workspace_variable_exists:
            logging.info(f"Workspace Variable '{sensitive_variable['variable_key']}' already exists for workspace: {sensitive_variable['workspace_name']}, skipped.")
            continue

        workspace_id = target.workspaces.show(sensitive_variable['workspace_name'])['data']['id']
        attributes =  {
            "key" :sensitive_variable['variable_key'],
            "category": sensitive_variable['variable_category'],
            "hcl": sensitive_variable['variable_hcl'],
            "sensitive": False
        }
        if "variable_value" in sensitive_variable:
            if isinstance(sensitive_variable['variable_value'], str):
                attributes['value'] = sensitive_variable['variable_value']
        if "variable_description" in sensitive_variable:
            if isinstance(sensitive_variable['variable_description'], str):
                attributes['description'] = sensitive_variable['variable_description']
        if "password" in sensitive_variable['variable_key'].lower() or "pass" in sensitive_variable['variable_key'].lower():
            attributes["sensitive"] = True
            
        payload = {
            "data": {
                "type": "vars",
                "attributes": attributes
            }
        }
        try:
            target.workspace_vars.create(workspace_id, payload)
        except TFCHTTPInternalServerError as error:
            logging.error(f"Status Code: {error.args[0]['errors'][0]['status']} | {error.args[0]['errors'][0]['title']}")
            continue
    logging.info(f"All Workspace Variables Successfully Created")

def nuke_target_workspace_variables(target):
    confirmation = input(f"Are you sure you want to delete all Workspace Variables for {target.account.get_current_org()} ORG at URL '{target._instance_url}'? [Y/N]:")
    if confirmation.lower() == 'y':
        logging.info("Deleting workspace variables...")
        target_variables = target.vars.list()["data"]
        total = len(target_variables)
        if target_variables:
            for target_variable in target_variables:
                target_variable_id = target_variable['id']
                target_workspace_id = target_variable['relationships']['configurable']['data']['id']
                target.workspace_vars.destroy(target_workspace_id, target_variable_id)
                logging.info(f"({target_variables.index(target_variable) + 1}/{total}): Workspace variable {target_variable['attributes']['key']}, from workspace {target_workspace_id}, deleted.")
        logging.info("Workspace variables deleted.")

def set_target_workspace_execution_mode(target, mode, name_identifier):
    logging.info(f"Updating {name_identifier} Workspaces' Execution Mode...")
    if mode == 'agent' and target._hostname != 'app.terraform.io':
        logging.warning(f"Execution Mode '{mode}' is not available for non TFC Workspaces.")
    else:
        if mode == 'agent':
            agent_pools = target.agents.list_pools()['data']
            agent_pool_id = None
            for agent_pool in agent_pools:
                if name_identifier in agent_pool['attributes']['name'].lower():
                    agent_pool_id = agent_pool['id']
                    break
            if not agent_pool_id:
                logging.error(f"Could not find correct Agent Pool to assign to Workspaces.")
                exit()
        workspaces = target.workspaces.list_all()['data']
        total = len(workspaces)
        if workspaces:
            for workspace in workspaces:
                logging.info(f"({workspaces.index(workspace) + 1}/{total}): Updating Workspace {workspace['attributes']['name']} execution mode to '{mode}'...")
                workspace_name = workspace['attributes']['name']
                if name_identifier in workspace_name.lower():
                    payload = {
                        "data": {
                            "attributes": {
                                "execution-mode": mode
                            },
                        },
                            "type": "workspaces"
                    }

                    if mode == 'agent':
                        payload['data']['attributes']['agent-pool-id'] = agent_pool_id

                    target.workspaces.update(payload, workspace_name)
                else:
                    logging.info(f"(Workspace {workspace['attributes']['name']} does not match identifier '{name_identifier}', skipped.'")
        logging.info("Workspaces' Execution Mode Updated.")

def migrate_workspaces(source, target):
    logging.info(f"Migrating Source Workspaces...")
    source_workspaces = source.workspaces.list_all()['data']
    total = len(source_workspaces)
    for source_workspace in source_workspaces:
        source_workspace_name = source_workspace['attributes']['name']

        try:
            source_workspace_vcs_id = source_workspace['attributes']['vcs-repo']['oauth-token-id']
            if source_workspace_vcs_id in TFE_SOURCE_VCS.values():
                source_workspace_vcs_type = list(TFE_SOURCE_VCS.keys())[list(TFE_SOURCE_VCS.values()).index(source_workspace_vcs_id)]  
            else:
                logger.error("Could not find VCS Identifier in hardcoded list of VCS Providers Dict.")
                exit()
        except:
            logging.debug(f"Workspace {source_workspace_name} is not connected to a VCS provider")
            source_workspace_vcs_type = None

        try:
            target.workspaces.show(source_workspace_name)
            logging.info(f"({source_workspaces.index(source_workspace) + 1}/{total}): Workspace {source_workspace_name} already exists on target.")
        except TFCHTTPNotFound as not_found:
            logging.info(f"({source_workspaces.index(source_workspace) + 1}/{total}): Creating Workspace {source_workspace_name} on TFC Target...")
            new_workspace_payload = {
                "data": {
                    "attributes": {
                        "name": source_workspace_name,
                        "terraform_version": source_workspace["attributes"]["terraform-version"],
                        "working-directory": source_workspace["attributes"]["working-directory"],
                        "file-triggers-enabled": \
                            source_workspace["attributes"]["file-triggers-enabled"],
                        "allow-destroy-plan": source_workspace["attributes"]["allow-destroy-plan"],
                        "auto-apply": source_workspace["attributes"]["auto-apply"],
                        "execution-mode": source_workspace["attributes"]["execution-mode"],
                        "description": source_workspace["attributes"]["description"],
                        "source-name": source_workspace["attributes"]["source-name"],
                        "source-url": source_workspace["attributes"]["source-url"],
                        "queue-all-runs": source_workspace["attributes"]["queue-all-runs"],
                        "speculative-enabled": \
                            source_workspace["attributes"]["speculative-enabled"],
                        "trigger-prefixes": source_workspace["attributes"]["trigger-prefixes"],
                    },
                    "type": "workspaces"
                }
            }
            
            if source_workspace_vcs_type is not None:
                if source_workspace_vcs_type in TFC_TARGET_VCS:
                    new_workspace_payload["data"]["attributes"]["vcs-repo"] = {
                        "identifier": source_workspace["attributes"]['vcs-repo']['identifier'],
                        "oauth-token-id": TFC_TARGET_VCS[source_workspace_vcs_type],
                        "branch": source_workspace["attributes"]["vcs-repo"]["branch"],
                        "default-branch": True if source_workspace["attributes"]["vcs-repo"]["branch"] == "" else False,
                        "ingress-submodules": source_workspace["attributes"]["vcs-repo"]["ingress-submodules"]
                    }
                else:
                    logging.warning(f"VCS Type '{source_workspace_vcs_type}' in VCS library, skipped.")
                    continue

            try:
                target.workspaces.create(new_workspace_payload)
                logging.info(f"Workspace {source_workspace_name} has been created.")
            except TFCHTTPBadRequest as error: 
                logging.error(f"Status Code: {error.args[0]['errors'][0]['status']} | {error.args[0]['errors'][0]['detail']}")
                logging.debug(f"New Workspace Payload: {new_workspace_payload}")
                for attempt in range(5):
                    logging.warning(f"Failed to create Workspace '{source_workspace_name}'. Re-attempt in 30 Seconds...")
                    time.sleep(30)
                    logging.warning(f"Retry Attempt: {attempt + 1}/5 to Create Workspace '{source_workspace_name}'.")
                    try:
                        target.workspaces.create(new_workspace_payload)
                        logging.info(f"Workspace {source_workspace_name} has been created.")
                        break
                    except TFCHTTPBadRequest as error: 
                        logging.error(f"Status Code: {error.args[0]['errors'][0]['status']} | {error.args[0]['errors'][0]['detail']}")
                        logging.debug(f"New Workspace Payload: {new_workspace_payload}")

def apply_workspace_variable_sets(target):
    logging.info(f"Applying Variable Sets to Workspaces...")
    workspaces = target.workspaces.list_all()['data']
    total = len(workspaces)
    for workspace in workspaces:
        logging.info(f"({workspaces.index(workspace) + 1}/{total}): Applying Variables Sets to Workspace: {workspace['attributes']['name']}...")
        for var_set in TFC_TARGET_VAR_SETS:
            if var_set in workspace['attributes']['name'].lower():
                payload = {
                    "data": [
                        {
                            "type": "workspaces",
                            "id": workspace['id']
                        }
                    ]
                }
                target.var_sets.apply_varset_to_workspace(TFC_TARGET_VAR_SETS[var_set], payload)
                logging.info(f"Applied Variable Set '{TFC_TARGET_VAR_SETS[var_set]}' to Workspace: {workspace['attributes']['name']}")

def migrate_current_state(source, target):
    logging.info("Migrating current state versions...")
    workspaces = source.workspaces.list_all()['data']
    total = len(workspaces)
    for workspace in workspaces:
        logging.info(f"({workspaces.index(workspace) + 1}/{total}): Current state version for workspace: {workspace['attributes']['name']}, created.")
        current_source_version = None
        target_state_filters = [
            {
                "keys": ["workspace", "name"],
                "value":  workspace["attributes"]["name"]
            },
            {
                "keys": ["organization", "name"],
                "value": target.get_org()
            }
        ]

        target_state_versions =  target.state_versions.list_all(filters=target_state_filters)['data']
        target_state_version_serials = [state_version["attributes"]["serial"] for state_version in target_state_versions]

        try:
            current_source_version = source.state_versions.get_current(workspace['id'])["data"]
            current_source_version_number = current_source_version["attributes"]["serial"]
        except TFCHTTPNotFound:
            logging.info(f"Current state version for workspace: {workspace['attributes']['name']}, does not exist. Skipped.")
            continue

        if target_state_version_serials and current_source_version_number <= target_state_version_serials[0]:
            logging.info( f"State Version: {current_source_version_number}, for workspace {workspace['attributes']['name']}, exists or is older than the current version. Skipped.")
            continue
        
        context = ssl.create_default_context()

        if TFE_SOURCE_VERIFY is False:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        source_state_url = current_source_version["attributes"]["hosted-state-download-url"]
        source_pull_state = request.urlopen(source_state_url, data=None, context=context)
        source_state_data = source_pull_state.read()
        source_state_json = json.loads(source_state_data)
        source_state_serial = source_state_json["serial"]
        source_state_lineage = source_state_json["lineage"]

        source_state_hash = hashlib.md5()
        source_state_hash.update(source_state_data)
        source_state_md5 = source_state_hash.hexdigest()
        source_state_b64 = base64.b64encode(source_state_data).decode("utf-8")

        # Build the new state payload
        create_state_version_payload = {
            "data": {
                "type": "state-versions",
                "attributes": {
                    "serial": source_state_serial,
                    "md5": source_state_md5,
                    "lineage": source_state_lineage,
                    "state": source_state_b64
                }
            }
        }
        try:
            target_workspace = target.workspaces.show(workspace['attributes']['name'])['data']
        except TFCHTTPNotFound:
            logger.warn(f"Target Workspace '{workspace['attributes']['name']}' not found. Re-execute script with [--migrate-workspaces] parameter, skipped.")
            continue
        # Migrate state to the target workspace
        try:
            target.workspaces.lock(target_workspace['id'], {"reason": "migration script"})
        except TFCHTTPConflict:
            target.workspaces.force_unlock(target_workspace['id'])
            target.workspaces.lock(target_workspace['id'], {"reason": "migration script"})

        target.state_versions.create(target_workspace['id'], create_state_version_payload)
        target.workspaces.unlock(target_workspace['id'])

        logging.info(f"Current state version for workspace: {workspace['attributes']['name']}, created.")
    logging.info("Current state versions migrated.")

def create_target_registry_modules(source, target):
    logging.info("Migrating registry modules...")
    source_modules = source.registry_modules.list()['modules']
    total = len(source_modules)
    for source_module in source_modules:
        try:
            target.registry_modules.show(source_module['name'], source_module["provider"])["data"]
            logging.info(f"({source_modules.index(source_module) + 1}/{total}): Registry Module {source_module['name']} already exists on target.")
        except TFCHTTPNotFound as not_found:
            logging.info(f"({source_modules.index(source_module) + 1}/{total}): Creating Registry Module {source_module['name']} on TFC Target...")

            source_module_data = source.registry_modules.show(source_module['name'], source_module["provider"])["data"]
            try:
                registry_module_vcs_id = source_module_data['attributes']['vcs-repo']['oauth-token-id']
                if registry_module_vcs_id in TFE_SOURCE_VCS.values():
                    registry_module_vcs_type = list(TFE_SOURCE_VCS.keys())[list(TFE_SOURCE_VCS.values()).index(registry_module_vcs_id)]  
                else:
                    logger.error("Could not find VCS Identifier in hardcoded list of VCS Providers Dict.")
                    exit()
            except:
                logging.warning(f"Failed to identify VCS Repo for Registry Module '{source_module['name']}'. Will attempt migration with hardcoded default...")
                registry_module_vcs_type = TFE_SOURCE_DEFAULT_MODULE_VCS_PROVIDER

            # Build the new module payload
            new_module_payload = {
                "data": {
                    "attributes": {
                        "vcs-repo": {
                            "identifier": source_module_data["attributes"]["vcs-repo"]["identifier"],
                            "oauth-token-id": TFC_TARGET_VCS[registry_module_vcs_type],
                            "display_identifier": source_module_data["attributes"]["vcs-repo"]["display-identifier"]
                            }
                        },
                        "type": "registry-modules"
                    }
                }
            # Create the module in the target organization
            target.registry_modules.publish_from_vcs(new_module_payload)

    logging.info("Registry modules migrated.")

def migrate_teams(source, target):
    teams_map = {}

    # Fetch teams from existing org
    source_teams = source.teams.list()["data"]
    target_teams = target.teams.list()["data"]
    total = len(source_teams)

    target_teams_data = {}
    for target_team in target_teams:
        target_teams_data[target_team["attributes"]["name"]] = target_team["id"]

    new_org_owners_team_id = None

    for source_team in source_teams:
        if source_team["attributes"]["name"] == "owners":
            new_org_owners_team_id = source_team["id"]
            break

    for source_team in source_teams:        
        source_team_name = source_team["attributes"]["name"]

        if source_team_name in target_teams_data:
            teams_map[source_team["id"]] = target_teams_data[source_team_name]
            logging.info(f"({source_teams.index(source_team) + 1}/{total}): '{source_team['attributes']['name']}' already exists. Skipped.")
            continue

        if source_team_name == "owners":
            # No need to create a team, it's the owners team
            teams_map[source_team["id"]] = new_org_owners_team_id
        else:
            # Build the new team payload
            new_team_payload = {
                "data": {
                    "type": "teams",
                    "attributes": {
                        "name": source_team_name,
                        "organization-access": {
                            "manage-workspaces": source_team["attributes"]["organization-access"]["manage-workspaces"],
                            "manage-policies": source_team["attributes"]["organization-access"]["manage-policies"],
                            "manage-vcs-settings": source_team["attributes"]["organization-access"]["manage-vcs-settings"]
                        }
                    }
                }
            }

            # Create team in the target org
            logging.info(f"({source_teams.index(source_team) + 1}/{total}): Migrating '{source_team['attributes']['name']}' onto target.")
            new_team = target.teams.create(new_team_payload)
            logging.info(f"Team '{source_team_name}' has been created.")

            # Build Team ID Map
            teams_map[source_team["id"]] = new_team["data"]["id"]

    logging.info("Teams migrated.")

    logging.info("Migrating org memberships...")

    # Set proper membership filters
    active_member_filter = [
        {
            "keys": ["status"],
            "value": "active"
        }
    ]

    source_org_members = source.org_memberships.list_all_for_org(filters=active_member_filter)['data']
    target_org_members = target.org_memberships.list_all_for_org()['data']

    target_org_members_data = {}
    for target_org_member in target_org_members:
        target_org_members_data[target_org_member["attributes"]["email"]] = target_org_member["id"]

    org_membership_map = {}

    for source_org_member in source_org_members:
        source_org_member_email = source_org_member["attributes"]["email"]
        source_org_member_id = source_org_member["relationships"]["user"]["data"]["id"]

        if source_org_member_email in target_org_members_data:
            org_membership_map[source_org_member_id] = target_org_members_data[source_org_member_email]

            # TODO: should the team membership be checked for an existing org member
            # and updated to match the source_org value if different?
            logging.info(f"Org member: {source_org_member_email}, exists. Skipped.")
            continue

        for team in source_org_member["relationships"]["teams"]["data"]:
            team["id"] = teams_map[team["id"]]

        # Build the new user invite payload
        new_user_invite_payload = {
            "data": {
                "attributes": {
                    "email": source_org_member_email
                },
                "relationships": {
                    "teams": {
                        "data": source_org_member["relationships"]["teams"]["data"]
                    },
                },
                "type": "organization-memberships"
            }
        }

        # try statement required in case a user account tied to the email address does
        # not yet exist
        try:
            target_org_member = target.org_memberships.invite(new_user_invite_payload)["data"]
        except:
            org_membership_map[source_org_member["relationships"]["user"]["data"]["id"]] = None
            logging.info(f"User account for email: {source_org_member_email} does not exist. Skipped.")
            continue

        new_user_id = target_org_member["relationships"]["user"]["data"]["id"]
        org_membership_map[source_org_member["relationships"]["user"]["data"]["id"]] = new_user_id

    logging.info("Org memberships migrated.")

    logging.info("Migrating team access...")
    source_workspaces = source.workspaces.list_all()['data']
    total = len(source_workspaces)
    for source_workspace in source_workspaces:
        # Set proper workspace team filters to pull team access for each
        # workspace
        source_workspace_team_filters = [
            {
                "keys": ["workspace", "id"],
                "value": source_workspace['id']
            }
        ]

        # Pull teams from the old workspace
        source_workspace_teams = source.team_access.list(\
            filters=source_workspace_team_filters)["data"]

        try:
            target_workspace = target.workspaces.show(source_workspace['attributes']['name'])['data']
        except TFCHTTPNotFound as exception:
            logging.error(f"Workspace '{source_workspace['attributes']['name']}' does not exist on Target, skipping.")
            continue

        target_workspace_id = target_workspace['id']
        target_workspace_team_filters = [
            {
                "keys": ["workspace", "id"],
                "value": target_workspace_id
            }
        ]

        target_workspace_teams = target.team_access.list(filters=target_workspace_team_filters)["data"]
        target_team_ids = [team["relationships"]["team"]["data"]["id"] for team in target_workspace_teams]

        for source_workspace_team in source_workspace_teams:
            new_target_team_id = teams_map[source_workspace_team["relationships"]["team"]["data"]["id"]]

            if new_target_team_id in target_team_ids:
                logging.info(f"({source_workspaces.index(source_workspace) + 1}/{total}): '{new_target_team_id}' Team access for Workspace '{source_workspace['attributes']['name']}' exists. Skipped.")
                continue

            new_workspace_team_payload = {
                "data": {
                    "attributes": {
                        "access": source_workspace_team["attributes"]["access"]
                    },
                    "relationships": {
                        "workspace": {
                            "data": {
                                "type": "workspaces",
                                "id": target_workspace_id
                            }
                        },
                        "team": {
                            "data": {
                                "type": "teams",
                                "id": new_target_team_id
                            }
                        }
                    },
                    "type": "team-workspaces"
                }
            }

            if source_workspace_team["attributes"]["access"] == "custom":
                attributes_to_copy = [
                    "runs", "variables", "state-versions", "sentinel-mocks",
                    "workspace-locking"
                ]

                for attr in attributes_to_copy:
                    new_workspace_team_payload["data"]["attributes"][attr] = source_workspace_team["attributes"][attr]

            # Create the team workspace access map for the target workspace
            logging.info(f"({source_workspaces.index(source_workspace) + 1}/{total}): Adding Access for Team '{new_target_team_id}' to Workspace '{source_workspace['attributes']['name']}' on TFC Target...")
            target.team_access.add_team_access(new_workspace_team_payload)

    logging.info("Team access migrated.")

def handler(source, target, args):
    try:
        if args.migrate_teams:
            migrate_teams(source, target)
        else:
            logging.info(f"[--migrate-teams] argument not provided to create new teams, skipped.")

        if args.migrate_registry_modules:
            create_target_registry_modules(source, target)
        else:
            logging.info(f"[--migrate-registry-modules] argument not provided to migrate registry modules, skipped.")

        if args.migrate_workspaces:
            migrate_workspaces(source, target)
        else:
            logging.info(f"[--migrate-workspaces] argument not provided to create new workspaces, skipped.")

        if args.delete_workspace_vars:
            nuke_target_workspace_variables(target)
        else:
            logging.info(f"[--delete-workspace-vars] argument not provided to delete workspace variables, skipped.")

        if args.create_workspace_vars_csv:
            if args.output_file_path:
                create_source_variable_spreadsheet(source, args.output_file_path)
            else:
                logging.error(f"'Missing file path for Workspace Variables Parameter. [--output-file-path]")
                exit()
        else:
            logging.info(f"[--create-workspace-vars-csv] [--output-file-path] arguments not provided to create workspace variable spreedsheet, skipped.")

        if args.create_workspace_vars:
            deploy_target_workspace_variables(target, args.var_file_path)    
        else:
            logging.info(f"[--create-workspace-vars] argument not provided to create workspace variables, skipped.")

        if args.update_workspace_execution:
            if args.execution_mode:
                if args.workspace_identifier:
                    set_target_workspace_execution_mode(target, args.execution_mode, args.workspace_identifier)
                else:
                    logging.error(f"'Missing Workspace Identifier Parameter. [--workspace-identifier]")
                    exit()
            else:
                logging.error(f"'Missing Workspace Execution Mode Parameter. [--execution-mode]")
                exit()
        else:
            logging.info(f"[--update-workspace-execution] [--execution-mode] [--workspace-identifier] arguments not provided to updated workspace execution mode, skipped.")

        if args.update_workspace_varsets:
            apply_workspace_variable_sets(target)
        else:
            logging.info(f"[--update-workspace-varsets] argument not provided to updated workspace variable sets, skipped.")

        if args.migrate_current_state:
            migrate_current_state(source, target)
        else:
            logging.info(f"[--migrate-current-state] argument not provided to migrate current state versions, skipped.")
    except TFCHTTPUnclassified:
        logger.error("Unable to authenticate requests. Please verify proxy redirect.")
        exit()

if __name__ == "__main__":
    args = parse_arguments()
    log_level = logging.INFO

    if args.debug:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level)
    try:
        source = TFC(TFE_SOURCE_TOKEN, url=TFE_SOURCE_URL, verify=TFE_SOURCE_VERIFY, log_level=log_level)
        source.set_org(TFE_SOURCE_ORG)
        logging.info(f"Configured Source: Host '{source.get_hostname()}'; Organiztion '{source.get_org()}'")
        target = TFC(TFC_TARGET_TOKEN, url=TFC_TARGET_URL, verify=TFC_TARGET_VERIFY, log_level=log_level)
        target.set_org(TFC_TARGET_ORG)
        logging.info(f"Configured Target: Host '{target.get_hostname()}'; Organization '{target.get_org()}'")
    except json.JSONDecodeError as decoding_error:
        logging.error(f"Outgoing GET Request to '//.well-known/terraform.json' failed to acquire JSON data needed for migration steps.")
        exit()      

    handler(source, target, args)
    exit()