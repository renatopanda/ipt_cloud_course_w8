# MEI-IoT.ipt - Docker Swarm + GlusterFS + keepalived + minio + portainer + traefik

Note: this is a WIP with several parts unorganized. It is to be used under Windows (or other system) with Vagrant to launch several VMs. Each VM will have docker installed and then can be grouped as a docker swarm - so, it will not use the host system and docker desktop as base.

There are 3 nodes for swarm:
```bash
vagrant up

vagrant ssh node1

# In prod firewall rules should be setup to open ports

docker swarm init --advertise-addr 192.168.46.11
# save join token
```

We can use docker visualizer (or any other tool) to inspect the swarm visualy:
```bash
docker run -it -d -p 8080:8080 -v /var/run/docker.sock:/var/run/docker.sock dockersamples/visualizer

```
This is just running a docker container inside one of the nodes, it was not deployed to the swarm.
Check: http://192.168.46.11:8080/

No container is running in the swarm because the docker visualizer is running outside of the swarm.

Stop and deploy again to the swarm:
```bash
docker ps # check the hash of the viz container
docker stop <id> # stop

# deploy to swarm
docker service create \
  --name=viz \
  --publish=8080:8080/tcp \
  --constraint=node.role==manager \
  --mount=type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock \
  dockersamples/visualizer

```

Now, for each worker, run:
```bash
vagrant ssh node2
docker swarm join --token <join-token> 192.168.46.11:2377
```

## Deploy app using compose
```bash
cd /vagrant/demo1
docker stack deploy -c docker-compose.yml demo
```

## Build and deploy app using compose

```bash
cd /vagrant/demo2
docker compose build
docker stack deploy -c docker-compose.yml demo2 # this will fail, why?
```

Docker compose will ignore the build command when using swarm. Because a swarm consists of multiple Docker Engines, a registry is required to distribute images to all of them. You can use the Docker Hub or maintain your own.

```bash
docker service create --name registry --publish published=5000,target=5000 registry:2
docker service ls
curl http://localhost:5000/v2/
curl http://192.168.46.11:5000/v2/
curl http://192.168.46.12:5000/v2/
```

The expected output is `{}`.
This used the [registry image](https://hub.docker.com/_/registry) @ DockerHub. Please note that this is just the registry itself, without any auth* scheme configured and no UI part as available on DockerHub (that is another completely different project, see Harbor for and OSS version).

### Test again, first locally:
```bash
docker compose build
docker compose up # check errors, why?
# open http://192.168.46.11 (will not work on http://192.168.46.12, why?)

docker compose down --volumes
```

### Push to local registry and deploy to swarm
```bash
docker compose build
docker compose push
docker stack deploy -c docker-compose.yml demo2
```
Check http://192.168.46.11

It works! Also, LB and service discovery? :-)

## Start and stop services
Swarm does not balance nodes automatically, so suspend and resume one and check the visualization:
```bash
vagrant suspend node2
vagrant up node2
```
All containers were moved out of node2, but are not moved again.
```bash
docker service update --force <servicename>
```
https://www.kevsrobots.com/learn/docker_swarm/09_rebalancing.html

## Multiple services
```bash
vagrant ssh node1
cd /vagrant/demo3

# build and run with composer
docker compose up -d

# check it is running
docker compose ps

# check with curl
curl http://localhost:8000
curl http://192.168.46.11:8000
# Or visit: http://192.168.46.11:8000

# stop the stack
docker compose down --volumes
```

### Important things to check
1. Why ADD vs COPY in Dockerfile?
2. Why "redis" app.py line  5?

## Build and push the image again
```bash
# using docker compose
docker compose push

# or step by step
docker build -t 127.0.0.1:5000/counter:latest .

# Push the Docker image to the local registry
docker push 127.0.0.1:5000/counter:latest

# Check the images at our registry
curl -X GET http://127.0.0.1:5000/v2/_catalog
curl -X GET http://127.0.0.1:5000/v2/counter/tags/list

# Now deploy the stack
docker stack deploy --compose-file compose.yml counter_demo
```

It is running!
```bash
docker stack ls
docker stack services counter_demo
docker service ps counter_demo_web

# If the previous demo is still running, check it too...
```

You can check it over:
* http://192.168.46.11:8000/
* http://192.168.46.12:8000/
* http://192.168.46.13:8000/

... but only one container is running. Why? Docker provides a built-in routing mesh, you can access any node in the swarm on port 8000 and get routed to the app.

### Scale services
docker service scale counter_demo_web=5

### Remove service

docker stack rm counter_demo

## Rolling updates
```bash
cd /vagrant/demo4

# Build and tag
docker build -t 127.0.0.1:5000/counter:latest -t 127.0.0.1:5000/counter:v1.0 .
# Tag again, just to demonstrate
docker tag 127.0.0.1:5000/counter:v1.0 127.0.0.1:5000/counter:stable

# check
docker image ls | grep counter

# Push the Docker image to the local registry
docker push 127.0.0.1:5000/counter:latest
docker push 127.0.0.1:5000/counter:v1.0
docker push 127.0.0.1:5000/counter:stable

# Check the registry (with jq for pretty print)
sudo apt install jq -y
curl -X GET http://127.0.0.1:5000/v2/counter/tags/list | jq
```
### Service updates

Now it is all build, lets deploy and learn how to update:

```bash
docker stack deploy --compose-file compose.yml counter-again
```

Now edit the code of the app, rebuild and push:
```bash
# edit app.py to say v1.1
docker build -t 127.0.0.1:5000/counter:v1.1 .
# can we speed up builds? Check layers...

# Tag as latest
docker tag 127.0.0.1:5000/counter:v1.1 127.0.0.1:5000/counter:latest

# Push all, just in case you removed the registry container... (more on this later)
docker push 127.0.0.1:5000/counter:v1.1
docker push 127.0.0.1:5000/counter:v1.0
docker push 127.0.0.1:5000/counter:stable
docker push 127.0.0.1:5000/counter:latest

# probably would create a script to automatize all these steps...

curl -X GET http://127.0.0.1:5000/v2/counter/tags/list | jq
```

All set, now check the services. We want to update the web app to use the v1.1 image.
```bash
docker stack services counter-again

# apply update
docker service update --image 127.0.0.1:5000/counter:v1.1 counter-again_web

# if it fails, check details...
docker service inspect --pretty counter-again_web
docker service update counter-again_web # and restart
```

Try hitting refresh during updates to check for downtime... what happens?

## Problems
1. The registry is saving images locally (container layer). What happens if we remove it or it goes down or moved to another node?
2. What happens if I scale or move redis to another node?

## Extra
```bash
docker stack deploy -c minio-compose.yml minio
docker stack deploy -c portainer-compose.yml portainer
docker stack deploy -c traefik-compose.yml traefik
```

Minio: Access Minio on http://<manager-ip>:9001 with credentials minio/minio123.

Portainer: Access Portainer on http://<manager-ip>:9002.

Traefik: Access the Traefik dashboard on http://<manager-ip>:8082.

```bash
docker stack rm minio
docker stack rm portainer
docker stack rm traefik
```

## GlusterFS

What is GlusterFS?
https://docs.gluster.org/en/latest/Quick-Start-Guide/Architecture/

Plan:
* 3 VMs with 2 HDDs each (OS and GlusterFS)
  * To save resources, one could use GlusterFS on the docker VMs too.
* GlusterFS cluster
* keepalived with VIP addr for cluster access
* mount glusterFS partition on swarm nodes w/ VIP addr
* Docker stack mapping to glusterFS?

### Add VMs
```ruby
  # GlusterFS nodes
  (1..3).each do |i|
    config.vm.define "gluster#{i}" do |gluster|
      gluster.vm.box = "ubuntu/bionic64"
      gluster.vm.network "private_network", ip: "192.168.46.2#{i}"
      gluster.vm.provider "virtualbox" do |vb|
        vb.memory = "512"
        vb.cpus = 1
        vb.customize ["createhd", "--filename", "gluster#{i}_disk.vdi", "--size", "10240"]
        vb.customize ["storageattach", :id, "--storagectl", "SATA Controller", "--port", "1", "--device", "0", "--type", "hdd", "--medium", "gluster#{i}_disk.vdi"]
      end
      gluster.vm.provision "shell", inline: <<-SHELL
        apt-get update
        apt-get install -y glusterfs-server
        systemctl start glusterd
        systemctl enable glusterd
        mkfs.ext4 /dev/sdb
        mkdir -p /gluster/brick1
        echo '/dev/sdb /gluster/brick1 ext4 defaults 0 0' | sudo tee -a /etc/fstab
        mount -a
      SHELL
    end
  end
```

### Prepare disks on Gluster nodes

Repeat on every gluster node:
```bash
vagrant ssh gluster<X> # gluster1, 2, ...
sudo lsblk # check if sdb is present (or if a different name is used)
sudo fdisk /dev/sdb # create new partition (press g, n, then default values, finally w)
sudo parted /dev/sdb --script mklabel gpt
sudo parted /dev/sdb --script mkpart primary xfs 0% 100%
sudo mkfs.xfs -i size=512 /dev/sdb1 # format the new partition (sdb1) with XFS - could be ext4?
sudo mkdir /mnt/glusterfs # mounting point for the new partition
sudo mount /dev/sdb1 /mnt/glusterfs # (this mounts and is used in next steps)

sudo lsblk # confirm that it is mounted, should see something like
sdb                         8:16   0   10G  0 disk
└─sdb1                      8:17   0   10G  0 part /mnt/glusterfs

# we could edit /etc/fstab to mount the disk...
# echo '/dev/sdb1 /mnt/glusterfs xfs defaults 0 0' | sudo tee -a /etc/fstab
# but mount the partition by UUID ensures it works even if the device name changes later on
UUID=$(sudo blkid -s UUID -o value /dev/sdb1)
echo "UUID=${UUID} /mnt/glusterfs xfs defaults 0 0" | sudo tee -a /etc/fstab
# NOTE: there is a nice comment somewhere (github link above) about using systemd instead of fstab directly.

# check if there are no errors *related with /dev/sdb1*
sudo findmnt --verify

# finally, mount again
sudo mount -a
df -h /mnt/glusterfs/

# create the folfer where each brick will be stored
sudo mkdir -p /mnt/glusterfs/vol1-brick<N> # N = number of the node
```

### Install and enable GlusterFS
```bash
sudo apt update -y
sudo apt-get install glusterfs-server
sudo systemctl start glusterd
sudo systemctl enable glusterd

sudo systemctl status glusterd # should be active (running)
```

### Form the GlusterFS Cluster
```bash
# Enter node gluster1
vagrant ssh gluster1

# From gluster1 probe other nodes
# in prod iptables must be setup...
sudo gluster peer probe 192.168.46.22
sudo gluster peer probe 192.168.46.23
sudo gluster peer status

sudo gluster pool list

# This uses disperse with redundancy 1, one could use only two VMs with replication and VIP.
sudo gluster volume create gluster-vol1 disperse 3 redundancy 1 192.168.46.21:/mnt/glusterfs/vol1-brick1 192.168.46.22:/mnt/glusterfs/vol1-brick2 192.168.46.23:/mnt/glusterfs/vol1-brick3

sudo gluster volume start gluster-vol1
sudo gluster volume info  gluster-vol1
```

### Mount GlusterFS Volume on Docker Nodes (clients)
```bash
sudo apt-get update
sudo apt-get install -y glusterfs-client
sudo mkdir -p /mnt/gluster-vol1
# this will mount using the IP of the first GlusterFM, if it fails storage goes down, one could use a VIP between the GlusterFS nodes (also check the guide).
echo "192.168.46.21:/gluster-vol1  /mnt/gluster-vol1 glusterfs  defaults,_netdev       0 0" | sudo tee -a /etc/fstab
sudo mount -a
sudo df -h /mnt/gluster-vol1/
```

TODO: based on this, but updated. Continue migration to systemd and add keepalived + VIP
minio
https://gist.github.com/scyto/f4624361c4e8c3be2aad9b3f0073c7f9