#!/bin/bash

set -e

echo "Checking if sde1 target disk is present"
if [ ! -b /dev/sde1 ]; then
    echo "Error: /dev/sde1 not found. Please insert the USB drive or mount using usbipd."
    exit 1
fi

export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-

echo "Building kernel"
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE} Image

echo "Building modules"
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE} modules

echo "Building device tree blobs"
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE} dtbs

echo "Mounting USB drive t80usb"
sudo mount /dev/sde1 /mnt/t80usb/

echo "Deploying kernel and device tree blobs to t80usb"
sudo rm /mnt/t80usb/boot/linux-mainline-69/*
sudo cp arch/arm64/boot/dts/freescale/fsl-ls1043a-*.dtb /mnt/t80usb/boot/linux-mainline-69/
sudo cp arch/arm64/boot/Image /mnt/t80usb/boot/linux-mainline-69/

echo "Deploying modules to t80usb"
sudo make ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE} INSTALL_MOD_PATH=/mnt/t80usb modules_install

echo ""
echo "--- Contents of /mnt/t80usb/boot/linux-mainline-69/ ---"
ls -l /mnt/t80usb/boot/linux-mainline-69/
echo "---"
echo ""

echo "Syncing and unmounting t80usb"
sudo umount /mnt/t80usb
sudo eject /dev/sde

echo "Done"
