#!/usr/bin/env bash


# config
filepath="$HOME/.config/hca/config.ingest.json"
upload_service_url='https://upload.{deployment_stage}.archive.data.humancellatlas.org/v1'
prod_upload_service_url='https://upload.archive.data.humancellatlas.org/v1'
bucket_name_template='org-hca-data-archive-upload-{deployment_stage}'
original="$HOME/.config/hca/config.json"
backup="$HOME/.config/hca/config.json.bak"

show_some_help() {
    echo "This script will configure the HCA CLI to use the Ingest instance of the upload service. Add -u flag to unset and use DEFAULT configuration"
    echo "Usage: $0 [-h|-u]"
}

set_config() {
    if [[ ! -f "$backup" ]]; then
        cp $original $backup

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

        mv $filepath $original

        echo "HCA CLI is now configured to use the Ingest instance of the Upload Service"
    else
        echo "HCA CLI is already configured to use the Ingest instance of the Upload Service"
    fi
}

unset_config(){
    if [[ -f "$backup" ]]; then
        mv $backup $original
        rm $backup
        echo "HCA CLI is now configured to use the DEFAULT configuration"
    else
        echo "HCA CLI is already configured to use the DEFAULT configuration"
    fi
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
