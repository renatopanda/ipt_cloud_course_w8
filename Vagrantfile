# -*- mode: ruby -*-
# vi: set ft=ruby :


Vagrant.configure("2") do |config|
  # Docker Swarm nodes
  (1..3).each do |i|
    config.vm.define "node#{i}" do |node|
      node.vm.box = "bento/ubuntu-22.04"
      node.vm.network "private_network", ip: "192.168.46.1#{i}"
      node.vm.hostname = "node#{i}"
      node.vm.provider "virtualbox" do |vb|
        vb.name = "Swarm Node #{i}"
        vb.memory = "1024"
        vb.cpus = 1
        # create a master VM before creating the linked clones
        vb.linked_clone = true
      end

      node.vm.provision "shell", inline: <<-SHELL
        apt-get update

        # Install Docker - https://docs.docker.com/engine/install/ubuntu/
        for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done
        # Add Docker's official GPG key:
        sudo apt-get update
        sudo apt-get install ca-certificates curl
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc

        # Add the repository to Apt sources:
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update

        # Install latest version
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        # Uso docker without sudo for the vagrant user
        usermod -aG docker vagrant

        # Test docker
        docker run hello-world
        SHELL
    end
  end


  # GlusterFS nodes
  gluster_vms = 3
  (1..gluster_vms).each do |i|
    config.vm.define "gluster#{i}" do |gluster|
      gluster.vm.box = "bento/ubuntu-22.04"
      gluster.vm.hostname = "gluster#{i}"
      gluster.vm.network "private_network", ip: "192.168.46.2#{i}"
      gluster.vm.disk :disk, name: "gluster#{i}_disk", size: "10GB"
      gluster.vm.provider "virtualbox" do |vb|
        vb.name = "GlusterFS Node #{i}"
        vb.memory = "1024"
        vb.cpus = 1
        vb.linked_clone = true
        #vb.customize ["createhd", "--filename", "gluster#{i}_disk.vdi", "--size", "10240"]
        #vb.customize ["storageattach", :id, "--storagectl", "SATA Controller", "--port", "1", "--device", "0", "--type", "hdd", "--medium", "gluster#{i}_disk.vdi"]
      end
      gluster.vm.provision "shell", inline: <<-SHELL
        sudo lsblk # check if sdb is present (or if a different name is used)
        # sudo fdisk /dev/sdb # create new partition (press g, n, then default values, finally w)
        sudo parted /dev/sdb --script mklabel gpt
        sudo parted /dev/sdb --script mkpart primary xfs 0% 100%
        sudo mkfs.xfs -i size=512 /dev/sdb1 # format the new partition (sdb1) with XFS - could be ext4?
        sudo mkdir /mnt/glusterfs # mounting point for the new partition
        sudo mount /dev/sdb1 /mnt/glusterfs # (this mounts and is used in next steps)
        UUID=$(sudo blkid -s UUID -o value /dev/sdb1)
        echo "UUID=${UUID} /mnt/glusterfs xfs defaults 0 0" | sudo tee -a /etc/fstab

        # check if there are no errors *related with /dev/sdb1*
        sudo findmnt --verify

        # finally, mount again
        sudo mount -a
        df -h /mnt/glusterfs/

        # folder to save each gluster volume brick
        sudo mkdir /mnt/glusterfs/vol1-brick#{i}

        # install and enable glusterfs
        sudo apt update -y
        sudo apt-get install glusterfs-server -y
        sudo systemctl start glusterd
        sudo systemctl enable glusterd

        sudo systemctl status glusterd # should be active (running)
      SHELL
    end
  end
end
