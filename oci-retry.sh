#!/usr/bin/env bash
#
# Auto-retry creation of a free Ampere A1 instance until capacity is available.
# Designed to run in **Oracle Cloud Shell** (Console → terminal icon, top-right),
# which is already authenticated — no API keys needed.
#
# Before running, create a file with your SSH *public* key (see the chat / README):
#   echo 'ssh-rsa AAAA... your-key' > ~/grabber.pub
#
# Then:  bash oci-retry.sh
#
set -u

# ---- Settings you can tweak ----
DISPLAY_NAME="Grabbertoullie"
OCPUS=2                       # drop to 1 + MEM_GB=6 if capacity is very tight
MEM_GB=12
SSH_PUB_KEY_FILE="$HOME/grabber.pub"
RETRY_SECONDS=60              # wait between attempts
# --------------------------------

COMPARTMENT_ID="${OCI_TENANCY:?Run this inside OCI Cloud Shell (OCI_TENANCY is not set)}"

if [ ! -f "$SSH_PUB_KEY_FILE" ]; then
  echo "ERROR: $SSH_PUB_KEY_FILE not found."
  echo "Create it first, e.g.:  echo 'ssh-rsa AAAA... your-key' > $SSH_PUB_KEY_FILE"
  exit 1
fi

echo "==> Discovering your subnet..."
SUBNET_ID=$(oci network subnet list --compartment-id "$COMPARTMENT_ID" | jq -r '.data[0].id')
echo "    subnet: $SUBNET_ID"

echo "==> Discovering the Ubuntu 22.04 Minimal aarch64 image..."
IMAGE_ID=$(oci compute image list \
  --compartment-id "$COMPARTMENT_ID" \
  --shape "VM.Standard.A1.Flex" \
  --operating-system "Canonical Ubuntu" \
  --sort-by TIMECREATED \
  | jq -r '[.data[] | select(.["display-name"] | test("22.04"))][0].id')
echo "    image: $IMAGE_ID"

echo "==> Discovering availability domains..."
mapfile -t ADS < <(oci iam availability-domain list --compartment-id "$COMPARTMENT_ID" | jq -r '.data[].name')
echo "    ADs: ${ADS[*]}"

if [ -z "$SUBNET_ID" ] || [ "$SUBNET_ID" = "null" ] || [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "null" ] || [ ${#ADS[@]} -eq 0 ]; then
  echo "ERROR: could not auto-discover subnet/image/ADs. Check that your VCN+subnet exist."
  exit 1
fi

echo
echo "==> Retrying VM.Standard.A1.Flex ($OCPUS OCPU / ${MEM_GB}GB) every ${RETRY_SECONDS}s across all ADs."
echo "    Leave this tab open. Ctrl+C to stop."
echo

attempt=0
while true; do
  for AD in "${ADS[@]}"; do
    attempt=$((attempt + 1))
    echo "[$(date +%H:%M:%S)] attempt #$attempt in $AD ..."
    if oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AD" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config "{\"ocpus\":$OCPUS,\"memoryInGBs\":$MEM_GB}" \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --display-name "$DISPLAY_NAME" \
        --ssh-authorized-keys-file "$SSH_PUB_KEY_FILE" \
        --wait-for-state RUNNING 2>/tmp/oci_err; then
      echo
      echo "========================================================"
      echo " SUCCESS! Instance '$DISPLAY_NAME' is RUNNING in $AD."
      echo " Find its public IP:  Console → Compute → Instances"
      echo "========================================================"
      exit 0
    fi
    if grep -qi "capacity" /tmp/oci_err; then
      echo "    still out of capacity."
    else
      echo "    launch failed (non-capacity error):"
      sed 's/^/    /' /tmp/oci_err
      echo "    ^ fix the above, then re-run. Continuing to retry..."
    fi
    sleep "$RETRY_SECONDS"
  done
done
