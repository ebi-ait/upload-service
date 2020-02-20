#!/usr/bin/env bash

# config

filepath="$HOME/.config/hca/config.ingest.json"
upload_service_url='https://upload.{deployment_stage}.archive.data.humancellatlas.org/v1'
prod_upload_service_url='https://upload.archive.data.humancellatlas.org/v1'
bucket_name_template='org-hca-data-archive-upload-{deployment_stage}'
original='~/.config/hca/config.json'

show_some_help() {
    echo "This script will configure the HCA CLI to use the Ingest instance of the upload service"
}

set_config() {
    touch $filepath
    echo "{
  \"upload\": {
    \"preprod_api_url_template\": \"$upload_service_url\",
    \"current_area\": null,
    \"bucket_name_template\": \"$bucket_name_template\",
    \"upload_service_api_url_template\": \"$upload_service_url\",
    \"production_api_url\": \"$prod_upload_service_url\"
  }
}
" > $filepath

    export HCA_CONFIG_FILE=$filepath

    echo "HCA CLI is now configured to use the Ingest instance of the Upload Service"
}

unset_config(){
    export HCA_CONFIG_FILE=$original
    if [[ -f "$filepath" ]]; then
      rm $filepath
    fi
    echo "HCA CLI is now configured to use the DEFAULT configuration"
}

has_u_option=false

OPTIND=1
while getopts hu opt; do
    case $opt in
        h) show_some_help;
        ;;
        u) unset_config
        ;;
        *) echo "Unknown option -$OPTARG";
        ;;
    esac
done

if [ $OPTIND -eq 1 ]; then set_config; fi

shift $((OPTIND-1))
