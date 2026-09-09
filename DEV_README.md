Personal prototype

## LOCAL TESTING 
- sudo docker build --network=host -t local-test-pipeline .

# Image bauen
docker build --progress=plain -t stemgen:test .

# Direkt im Container testen
docker run --rm stemgen:test deno --version
docker run --rm stemgen:test yt-dlp --version

# Vollständigen Start testen
docker run --rm \
    -p 7860:7860 \
    -e MAGENTA_USER="deinuser" \
    -e MAGENTA_PASS_OBFUSCATED="obfusciert" \
    stemgen:test

# GitHub als Docker-"Provider" für Runpod
For a reliable Europe setup (and to get off the same failing site), I’d prioritize these datacenters for an RTX 4090 pod:
1) EU-RO-1 (best current availability signal: Medium) -> Datacenter IP BLACKLISTED @ Youtube
2) EU-CZ-1 (Low, up in less than 5 minutes!)-> Datacenter IP BLACKLISTED @ Youtube
3) EUR-NO-1 (Low)
DNU: EUR-IS-2 is wasting money, due to loading hours > 30 Minutes and unexpected interruptions of download!
SE Blacklisted...  FR auch toto
# EU-NL-1 working!

# Image prüfen
docker images | grep stemgen

# Exponierte Ports checken
docker inspect stemgen:test --format '{{json .Config.ExposedPorts}}'

# Starten (Port anpassen)
docker run -d --name stemgen --gpus all -p 8080:<port> --restart unless-stopped stemgen:test