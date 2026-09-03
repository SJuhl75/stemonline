#!/usr/bin/env bash

set -u

LIBRARY_DIR="${1:-.}"
STEMS_DIR="${LIBRARY_DIR}/Engine Library/Stems"
DATABASE_DIR="${LIBRARY_DIR}/Engine Library/Database2"
REPORT_FILE="${2:-engine-stems-report.txt}"

{
    echo "Engine-DJ-Stem-Untersuchung"
    echo "Datum: $(date --iso-8601=seconds)"
    echo "Library: ${LIBRARY_DIR}"
    echo

    echo "=== System ==="
    uname -a
    echo

    echo "=== Dateien ==="
    find "${STEMS_DIR}" \
        -maxdepth 1 \
        -type f \
        -name "*.stems" \
        -printf "%s bytes  %p\n" \
        | sort -n
    echo

    echo "=== Dateitypen ==="
    file "${STEMS_DIR}"/*.stems
    echo

    echo "=== m.db UUID ==="
    sqlite3 "${DATABASE_DIR}/m.db" \
        "SELECT * FROM Information;"
    echo

    echo "=== stm.db UUID ==="
    sqlite3 "${DATABASE_DIR}/stm.db" \
        "SELECT * FROM Information;"
    echo

    echo "=== Track-Zuordnung aus m.db ==="
    sqlite3 -header -column "${DATABASE_DIR}/m.db" \
        "SELECT id, path, filename, title, artist, fileType, length, fileBytes, isAnalyzed FROM Track ORDER BY id;"
    echo

    echo "=== PerformanceData aus m.db ==="
    sqlite3 -header -column "${DATABASE_DIR}/m.db" \
        "SELECT trackId, length(trackData), length(overviewWaveFormData), length(beatData), length(quickCues), length(loops) FROM PerformanceData ORDER BY trackId;"
    echo

    echo "=== MP4Box-Informationen ==="
    for file in "${STEMS_DIR}"/*.stems; do
        echo
        echo "--- ${file} ---"

        if command -v MP4Box >/dev/null 2>&1; then
            MP4Box -info "${file}" 2>&1 || true
        else
            echo "MP4Box nicht installiert."
        fi
    done

    echo
    echo "=== FFprobe-Informationen ==="
    for file in "${STEMS_DIR}"/*.stems; do
        echo
        echo "--- ${file} ---"

        if command -v ffprobe >/dev/null 2>&1; then
            ffprobe \
                -hide_banner \
                -v error \
                -show_entries \
                "format=duration,size,bit_rate:stream=index,codec_name,profile,sample_rate,channels,channel_layout,bit_rate" \
                -of default=noprint_wrappers=1 \
                "${file}" 2>&1 || true
        else
            echo "ffprobe nicht installiert."
        fi
    done

    echo
    echo "=== SHA256 ==="
    sha256sum "${STEMS_DIR}"/*.stems

} | tee "${REPORT_FILE}"

echo
echo "Report gespeichert unter:"
echo "${REPORT_FILE}"