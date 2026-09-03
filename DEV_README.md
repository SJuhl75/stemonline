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