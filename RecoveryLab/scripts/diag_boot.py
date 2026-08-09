"""
diag_boot.py — Diagnóstico de solo lectura del boot sector NTFS
Lee UNICAMENTE 512 bytes del offset de la partición.
No escribe nada. No modifica nada.
Requiere: ejecutar como Administrador

Uso:
    python diag_boot.py                  # Usa PHYSICALDRIVE2, offset 16 MB
    python diag_boot.py 1 1048576        # PHYSICALDRIVE1, offset 1 MB

Historia:
    Creado durante Validation Cycle 001 para diagnosticar
    el disco TOSHIBA MK5065GSX 500GB (PHYSICALDRIVE2).
"""

import struct
import sys

DEFAULT_DRIVE = r"\\.\PHYSICALDRIVE2"
DEFAULT_OFFSET = 16_777_216  # 16 MB — inicio de la partición 2 del Toshiba
SECTOR_SIZE = 512


def main():
    drive = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DRIVE
    # Allow offset as second argument (in bytes)
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OFFSET

    # Normalize drive path
    if not drive.startswith(r"\\.\"):
        drive = r"\\.\PHYSICALDRIVE" + drive

    print("=" * 60)
    print("diag_boot.py — Diagnóstico NTFS (solo lectura)")
    print("=" * 60)
    print(f"\nDisco:     {drive}")
    print(f"Offset:    {offset:,} bytes ({offset / (1024**2):.1f} MB)")
    print(f"Lectura:   {SECTOR_SIZE} bytes (1 sector)\n")

    try:
        with open(drive, "rb") as f:
            f.seek(offset)
            sector = f.read(SECTOR_SIZE)
    except PermissionError:
        print("ERROR: Necesitás ejecutar esto como Administrador.")
        print("  Click derecho en CMD → Ejecutar como administrador")
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: No se pudo abrir el disco: {e}")
        sys.exit(1)

    if len(sector) < SECTOR_SIZE:
        print(f"ERROR: Se leyeron solo {len(sector)} bytes en vez de {SECTOR_SIZE}")
        sys.exit(1)

    print("--- Sector leído correctamente ---\n")

    # Hex dump (first 64 bytes for visual inspection)
    print("--- Hex dump (primeros 64 bytes) ---")
    for row in range(4):
        start = row * 16
        hex_part = " ".join(f"{b:02X}" for b in sector[start:start+16])
        ascii_part = "".join(
            chr(b) if 32 <= b < 127 else "."
            for b in sector[start:start+16]
        )
        print(f"  {start:04X}: {hex_part}  {ascii_part}")
    print()

    # OEM ID (offset 3, 8 bytes)
    oem_id = sector[3:11].decode("ascii", errors="replace")
    is_ntfs = oem_id.startswith("NTFS")

    # Jump instruction (offset 0, 3 bytes)
    jump = sector[0:3]

    # Bytes per sector (offset 11, uint16)
    bytes_per_sector = struct.unpack_from("<H", sector, 11)[0]

    # Sectors per cluster (offset 13, uint8)
    sectors_per_cluster = sector[13]

    # Total sectors (offset 40, uint64)
    total_sectors = struct.unpack_from("<Q", sector, 40)[0]

    # MFT cluster number (offset 48, uint64)
    mft_cluster = struct.unpack_from("<Q", sector, 48)[0]

    # MFT mirror cluster number (offset 56, uint64)
    mft_mirror_cluster = struct.unpack_from("<Q", sector, 56)[0]

    # Clusters per MFT record (offset 64, int32)
    mft_record_clusters_raw = struct.unpack_from("<i", sector, 64)[0]

    # Clusters per index record (offset 68, int32)
    index_record_clusters_raw = struct.unpack_from("<i", sector, 68)[0]

    # Volume serial number (offset 72, uint64)
    serial = struct.unpack_from("<Q", sector, 72)[0]

    # Boot sector signature (offset 510, 2 bytes)
    signature = sector[510:512]

    # MFT record size calculation
    if mft_record_clusters_raw > 0:
        mft_record_size = mft_record_clusters_raw * sectors_per_cluster * bytes_per_sector
    else:
        mft_record_size = 2 ** abs(mft_record_clusters_raw)

    # Index record size
    if index_record_clusters_raw > 0:
        index_record_size = index_record_clusters_raw * sectors_per_cluster * bytes_per_sector
    else:
        index_record_size = 2 ** abs(index_record_clusters_raw)

    # MFT byte offset
    cluster_size = sectors_per_cluster * bytes_per_sector
    mft_byte_offset = offset + (mft_cluster * cluster_size)
    mft_mirror_byte_offset = offset + (mft_mirror_cluster * cluster_size)

    # Print results
    print(f"Firma OEM:           {oem_id!r}")
    print(f"Salto (jump):        {jump.hex()}")
    print(f"Firma NTFS:          {'SI — Boot sector NTFS presente' if is_ntfs else 'NO — No se encontro firma NTFS'}")
    print()
    print("--- Parametros NTFS ---")
    print(f"Bytes por sector:    {bytes_per_sector}")
    print(f"Sectores por cluster:{sectors_per_cluster}")
    print(f"Tamano de cluster:   {cluster_size:,} bytes ({cluster_size // 1024} KB)")
    print(f"Sectores totales:    {total_sectors:,}")
    print(f"Tamano del volumen:  ~{total_sectors * bytes_per_sector / (1024**3):.1f} GB")
    print()
    print("--- MFT (Master File Table) ---")
    print(f"Cluster del MFT:     {mft_cluster:,}")
    print(f"Offset del MFT:      {mft_byte_offset:,} bytes (~{mft_byte_offset / (1024**3):.2f} GB)")
    print(f"Cluster del MFTmirr: {mft_mirror_cluster:,}")
    print(f"Offset del MFTmirr:  {mft_mirror_byte_offset:,} bytes (~{mft_mirror_byte_offset / (1024**3):.2f} GB)")
    print(f"Tamano reg. MFT:     {mft_record_size:,} bytes")
    print(f"Tamano reg. indice:  {index_record_size:,} bytes")
    print()
    print("--- Otros ---")
    print(f"Numero de serie:     {serial:016X}")
    print(f"Firma 55 AA:         {'Correcta' if signature == b'\\x55\\xaa' else 'Ausente o corrupta'}")
    print()

    if is_ntfs and signature == b'\x55\xaa':
        print("=" * 60)
        print("RESULTADO: Boot sector NTFS INTEGRO")
        print("El MFT y su copia estan localizados. RecoveryLab puede trabajar.")
        print(f"El MFT esta a ~{mft_byte_offset / (1024**3):.2f} GB del inicio del disco.")
        print("=" * 60)
    elif is_ntfs:
        print("=" * 60)
        print("RESULTADO: Firma NTFS presente pero firma 55AA corrupta")
        print("El boot sector esta parcialmente danado.")
        print("Se puede intentar reparar o usar el MFT mirror como respaldo.")
        print("=" * 60)
    else:
        print("=" * 60)
        print("RESULTADO: Boot sector NO contiene firma NTFS")
        print("El boot sector esta corrupto o sobrescrito.")
        print("No significa que los datos esten perdidos — hay que buscar")
        print("el MFT por patron o usar el sector de respaldo.")
        print("=" * 60)


if __name__ == "__main__":
    main()
