#!/usr/bin/python3
# -*- coding: utf-8 -*-
from flask import Flask, request, make_response, Response
from datetime import datetime
import os
import json
import sys

import slack

# Slack client for Web API requests
slack_client = slack.WebClient(token=os.environ['SLACK_BOT_TOKEN'])
#SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]

# Flask web server for incoming traffic from Slack
app = Flask(__name__)
app.config.from_object("config.ProductionConfig")

# Backend route handling dialog response
@app.route("/dialog", methods=["POST"])
def create():
    #print(request.form)
    callback_payload = json.loads(request.form["payload"])
    command_user_id = callback_payload["user"]["id"]
    slack_domain = callback_payload["team"]["domain"]
    severity = callback_payload["submission"]["severity"]
    origin_channel_name = callback_payload["channel"]["name"]
    origin_channel_id = callback_payload["channel"]["id"]
    incident_name = callback_payload["submission"]["incident_name"]
    incident_manager_id = callback_payload["submission"]["incident_manager"]

    #Translate user ID as user name for user friendly message
    response = slack_client.users_profile_get(user = incident_manager_id)
    incident_manager_name = response["profile"]["real_name"]

    #Generate a unique incident channel name
    now = datetime.now()
    date_time = now.strftime("%Y%m%d-%H%M")
    incident_channel_name = severity+"-"+incident_name+"-"+date_time

    #Create channel
    response = slack_client.conversations_create(name = incident_channel_name)
    incident_channel_id = response["channel"]["id"]
    assert response["ok"]

    #List invited users
    if incident_manager_id != command_user_id:
        user_ids = command_user_id,incident_manager_id
    else: 
        user_ids = command_user_id

    #Invite people in it
    response = slack_client.conversations_invite(channel = incident_channel_id, users = user_ids)
    assert response["ok"]

    #Join command origin channel if not yet in it
    response = slack_client.conversations_join(channel=origin_channel_id)
    assert response["ok"]

    #Display a message with link to incident and incident master
    response = slack_client.chat_postMessage(
        channel="#"+origin_channel_name,
        #TODO display user friendly severity label
        text="Opening "+ severity +" incident in channel <https://"+ slack_domain +".slack.com/archives/"+ incident_channel_id +"|#"+ incident_channel_name +">, managed by <https://app.slack.com/team/"+ incident_manager_id+"|"+incident_manager_name +">!")
    assert response["ok"]

    return make_response("", 200)

#backend for /incident command management
@app.route("/incident", methods=["POST"])
def incident():
    #print(request.form)
    command_args = request.form["text"].split()
    command_type = command_args[0]
    command_user_id = request.form["user_id"]
    command_user_name = request.form["user_name"]
    command_trigger_id = request.form["trigger_id"]
    origin_channel_name = request.form["channel_name"] 
    origin_channel_id = request.form["channel_id"]

    #Join command origin channel if not yet in it
    response = slack_client.conversations_join(channel=origin_channel_id)
    assert response["ok"]

    if (command_type == "open"):
        #Push a dialog, callback will be done on /dialog
        response = slack_client.api_call(
            "dialog.open", 
            json={
                'trigger_id' : command_trigger_id,
                'dialog' : {
                    "title": "Create an incident",
                    "submit_label": "Submit",
                    "callback_id": command_user_id + "_incident_creation_form",
                    "elements": [
                        {
                            "type": "text",
                            "label": "Incident name",
                            "name": "incident_name"
                        },
                        {
                            "label": "Incident severity",
                            "type": "select",
                            "name": "severity",
                            "placeholder": "Select incident severity",
                            "options": app.config["SEVERITY_LEVELS"]
                        },
                        {
                            "label": "Incident manager",
                            "name": "incident_manager",
                            "type": "select",
                            "data_source": "users"
                        }
                    ]
                }
            }
        )
        assert response["ok"]

    elif (command_type == "list"):
        #Check if we also want to list closed incidents
        exclude_archived = 'true'
        if len(command_args) > 1 and command_args[1] == 'all':
            exlude_archived = 'false'

        #Get the channel list
        response = slack_client.conversations_list(
            exclude_archived = exclude_archived
        )

        #print(response)

        #Restrict to channel names matching redalert channels

        #Display a message listing incidents
        response = slack_client.chat_postMessage(
            channel="#"+origin_channel_name,
            text="Listing incidents"
        )
        assert response["ok"]
        #TODO

    elif (command_type == "close"):
        #Display a message explicitly saying incident is closed and by whom
        response = slack_client.chat_postMessage(
            channel="#"+origin_channel_name,
            text="<https://app.slack.com/team/"+command_user_id+"|"+command_user_name+"> closed this incident."
        )
        assert response["ok"]

        response = slack_client.conversations_archive(
            channel=origin_channel_id                
        )
        assert response["ok"]

    else:
        #Wrong command argument
        response = slack_client.chat_postMessage(
            channel="#"+origin_channel_name,
            text="Wrong command, only type '/incident open', '/incident list' or '/incident close')")
        assert response["ok"]

    return make_response("", 200)        

def main():
    app.run(host='0.0.0.0', port=3000)
    sys.exit()

if __name__ == '__main__':
    main()
