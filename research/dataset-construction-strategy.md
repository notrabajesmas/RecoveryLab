# Dataset Construction Strategy for Data Recovery Decision Engine

## Research Report — Comprehensive Findings

---

## 1. Existing Datasets for Data Recovery Research

### 1.1 NIST CFReDS (Computer Forensic Reference Data Sets)

**URL:** https://cfreds.nist.gov

The NIST CFReDS portal is the primary gateway to documented digital forensic image datasets maintained by the U.S. National Institute of Standards and Technology. Key characteristics:

- **Purpose:** Tool testing, developing familiarity with tool behavior, general practitioner training
- **Contents:** Documented disk images with known contents for forensic verification
- **Notable datasets:** "Hacking Case" — a well-known scenario-based forensic image
- **Limitations for recovery research:** These images are primarily designed for **forensic tool validation**, not for testing recovery from damaged or corrupted media. They represent intact or deliberately modified images (e.g., deleted files, hidden partitions) rather than physically damaged or corrupted filesystems.

### 1.2 Digital Corpora

**URL:** https://digitalcorpora.org/corpora/disk-images

Digital Corpora is the most significant public resource for disk images in forensics research:

- **NPS Test Disk Images:** Created specifically for testing computer forensic tools. These images are **free of non-public PII** and approved for release to the general public. NPS-created data is public domain.
- **169 disk images totaling 1.106 TB** (as cataloged by Breitinger et al., 2017)
- **Includes:** Real-world and experiment-generated images
- **Key limitation:** Most images are of **intact filesystems** with deleted or hidden data — not damaged or corrupted media. The focus is on forensic analysis (finding evidence), not recovery from physical/logical damage.

### 1.3 Enron Email Corpus

**URL:** Available via Digital Corpora and Library of Congress (https://www.loc.gov/item/2018487913)

- **Size:** ~44 GB of email data from ~150 users (mostly senior management)
- **Content:** ~500,000 messages organized into folders
- **Relevance:** Primarily used for email forensics and text mining research, not disk recovery
- **Limitation:** Not a damaged disk image — it's a structured email dataset

### 1.4 DFRWS (Digital Forensics Research Workshop) Challenge Datasets

- DFRWS has published challenge datasets for various years (2005-2023)
- These include disk images, memory dumps, and network captures for specific forensic challenges
- Available at: https://www.dfir.training/downloads/test-images

### 1.5 Forensic Focus / Forensics Wiki Corpora

**URL:** https://forensics.wiki/forensic_corpora

- Aggregates links to various forensic corpora including:
  - Compression algorithm test corpora
  - Training scenario disk images with packet captures
  - Testing images from SourceForge

### 1.6 Breitinger Forensic Datasets Catalog

**URL:** https://datasets.fbreitinger.de/datasets

A comprehensive catalog of 169+ disk images and other forensic datasets. Key findings from the seminal 2017 paper (Grajeda et al., "Availability of datasets for digital forensics – And what is missing", cited 191 times):

- **Most user-generated datasets originated from four repositories:** Digital Corpora, Enron E-mail Dataset, and two others
- **Major gap identified:** There is a critical lack of datasets representing **damaged or corrupted storage media** — the exact type needed for recovery research
- **The paper explicitly calls out the need for more realistic datasets** that represent the challenges of real-world digital forensics

### 1.7 Critical Gap Assessment

**No public datasets exist specifically for data recovery from damaged/corrupted storage media.** All existing forensic datasets focus on:
- Finding deleted/hidden files on intact filesystems
- Tool validation for forensic analysis
- Training scenarios for evidence collection

None represent:
- Physically damaged disk images (bad sectors, head crashes)
- Corrupted filesystem structures (MFT damage, inode table corruption)
- SSD-specific failure modes (TRIM erasure, firmware panic, controller failure)
- RAID degradation scenarios
- Multi-layered failure scenarios

---

## 2. How Professional Labs Build Their Knowledge

### 2.1 Knowledge Accumulation Model

Professional data recovery labs (DriveSavers, Ontrack/Kroll, Rossmann Group, Gillware) operate on a **proprietary knowledge model**:

- **Internal case databases:** Each lab maintains a private database of cases, outcomes, and techniques. As one Reddit AMA from a data recovery technician noted: *"Data Recovery is by nature a very secretive business, there is a lot of proprietary information, a lot of stuff that isn't shared."*
- **Apprenticeship model:** New technicians learn through hands-on mentorship, not textbooks. The field is described as "a craft" requiring "skilled craftsmen" rather than formal scientific training.
- **Failure pattern recognition:** Experienced technicians develop intuition for failure patterns based on thousands of cases. This tacit knowledge is rarely codified or shared.

### 2.2 Training and Certification Programs

**Certified Data Recovery Professional (CDRP)** — IACRB:
- 2-day course covering logical recovery methods
- Modules: Logical recovery of disabled hard drives, file format recognition tools, recovery via avoiding BIOS limitations
- Uses tools like R-Studio for logical recovery
- Covers basic circuit board replacements
- Exam: 1-hour certification test

**Rossmann Group Advanced Certification:**
- 6-day advanced program specializing in complex hard drive data recovery
- Focuses on firmware repair, advanced mechanical procedures, and component-level repair
- More hands-on and practical than CDRP

**DriveSavers Training:**
- Engineers are trained on recovering data from firmware and physical failures, software corruption, and encrypted devices
- SOC 2 Type II certified (security and compliance focus)
- Training is entirely internal and proprietary

**General training path** (from career guidance sources):
1. Develop practical skills with old/damaged storage devices
2. Set up a home lab with recovery tools and hardware
3. Volunteer or intern at repair shops
4. Obtain CDRP or similar certification
5. Build expertise through years of hands-on experience

### 2.3 Key Insight for Dataset Construction

The professional recovery industry's knowledge is **largely tacit and proprietary**. This creates both a challenge and an opportunity:
- **Challenge:** No structured, labeled datasets exist from professional labs
- **Opportunity:** Codifying this tacit knowledge into a structured dataset would be a genuinely novel contribution
- **Approach:** Partner with independent technicians (not the big labs) who may be more willing to share anonymized case data

---

## 3. Disk Image Generation for Testing

### 3.1 Controlled Filesystem Corruption

**Approach:** Create a known-good disk image, then systematically corrupt specific structures:

| Filesystem | Target Structure | Corruption Method |
|-----------|-----------------|-------------------|
| NTFS | MFT (Master File Table) | Zero out MFT entries, corrupt MFT mirror |
| NTFS | Boot sector / $Boot | Overwrite BPB fields |
| ext4 | Superblock | Corrupt primary superblock, test backup superblocks |
| ext4 | Inode table | Zero inode entries, corrupt inode bitmaps |
| FAT32 | FAT tables | Corrupt FAT1/FAT2 entries |
| HFS+ | Catalog file | B-tree node corruption |
| APFS | Container superblock | NX block corruption |

**Tools:**
- **Hex editors** (wxHexEditor, HxD) for targeted byte-level corruption
- **Custom Python scripts** using `struct` module for precise structure manipulation
- **`dd`** for overwriting specific offsets: `dd if=/dev/zero of=image.img bs=1 seek=OFFSET count=SIZE conv=notrunc`

### 3.2 Simulating Bad Sectors

**Linux device-mapper approach** (from Stack Overflow discussions):
```bash
# Create a loop device with injected errors
dmsetup create faulty << EOF
0 $(blockdev --getsize /dev/loop0) linear /dev/loop0 0
$(blockdev --getsize /dev/loop0) 100 error
EOF
```

**Using `scsi_debug` kernel module:**
```bash
modprobe scsi_debug dev_size_mb=100 opts=2
# opts=2 enables error injection
```

**Using `dm-flakey`:**
```bash
# Create a flaky device that intermittently drops reads/writes
dmsetup create flaky << EOF
0 $(blockdev --getsize /dev/loop0) flakey /dev/loop0 0 60 1 drop_writes
EOF
```

**For disk images (not block devices):**
- Create a normal image file, then use `dd` to zero out specific sectors
- Use a custom FUSE filesystem that returns EIO for specific regions
- Modify the image file directly with Python to inject read errors in a virtual device

### 3.3 SSD TRIM Simulation Scenarios

Based on research from Elcomsoft and Rossman Group:

**Key SSD recovery scenarios:**
1. **TRIM not sent:** Recovery is generally possible using standard undelete techniques
2. **TRIM sent, DRAT (Deterministic Read After Trim) = 0:** Data may be recoverable from NAND chips directly (chip-off)
3. **TRIM sent, DRAT = 1, DZAT (Deterministic Zero After Trim) = 1:** Data is zeroed and unrecoverable
4. **Firmware panic:** Drive reports incorrect capacity (e.g., 8MB instead of 512GB); recovery requires firmware-level repair
5. **Controller failure:** NAND chips may be intact; chip-off recovery possible

**Simulation approach:**
- Create SSD images with known file sets
- Issue TRIM commands to specific file ranges
- Capture the resulting image state
- Document the SSD model, firmware version, and TRIM behavior
- Use QEMU with virtual NVMe devices to test TRIM behavior in controlled environments

### 3.4 Tools for Generating Test Disk Images

| Tool | Purpose | Notes |
|------|---------|-------|
| **FTK Imager** | Create forensic images (E01, dd) | Free, widely used in forensics |
| **`dd` / `dc3dd`** | Create raw disk images | dc3dd adds forensic hashing |
| **`qemu-img`** | Create VM disk images (qcow2, vmdk, raw) | Supports various formats |
| **`mke2fs`, `mkfs.ntfs`, `mkfs.vfat`** | Create filesystems on images | Full control over filesystem parameters |
| **`guestfish` / `libguestfs`** | Manipulate disk images without mounting | Batch operations on images |
| **`dmsetup`** | Device-mapper for error injection | Create faulty block devices |
| **Python + `struct`** | Custom corruption scripts | Precise binary manipulation |
| **`badblocks`** | Identify/simulate bad blocks | Part of e2fsprogs |
| **`dm-flakey`** | Intermittent I/O errors | Device-mapper target |

### 3.5 Recommended Test Image Generation Pipeline

```
1. Create base image: qemu-img create -f raw test.img 10G
2. Partition: fdisk/parted on loop device
3. Format filesystem: mkfs.ext4 / mkfs.ntfs
4. Populate with known file set (see Section 6)
5. Record checksums of all files
6. Unmount and create "golden" copy
7. Apply corruption scenario (scripted)
8. Document: corruption type, location, severity
9. Test recovery tools against corrupted image
10. Compare recovered files against golden checksums
```

---

## 4. SMART Data as Features

### 4.1 The Google Disk Failure Study (2007)

**Paper:** "Failure Trends in a Large Disk Drive Population" (Pinheiro et al., FAST '07)
**Cited by:** 1,268 times
**Scope:** Analysis of over 100,000 drives in Google's data centers

**Key SMART attributes correlated with failure:**

| SMART Attribute | ID | Correlation | Risk Increase |
|----------------|-----|-------------|---------------|
| **Scan Errors** | 5 | After first scan error, 39x more likely to fail within 60 days | Very High |
| **Reallocation Count** | 5 | Drive with reallocated sectors significantly more likely to fail | High |
| **Offline Reallocation** | 5 | Similar to reallocation count | High |
| **Probational Count** | 5 | Sectors awaiting reallocation | Moderate |

**Critical finding:** Despite high correlation, SMART parameters alone are **insufficient for predicting individual drive failures** because:
- 56% of failed drives showed no SMART warning signals
- Many drives with elevated SMART values did not fail
- The false positive rate makes individual prediction impractical

### 4.2 Backblaze SMART Analysis

**Blog:** "What SMART Stats Tell Us About Hard Drives" (2016)
**Scope:** Analysis of 40,000+ drives over multiple years

**Five SMART stats Backblaze uses for failure prediction:**

| SMART Stat | Attribute | Description |
|-----------|-----------|-------------|
| **SMART 5** | Reallocated Sectors Count | Count of reallocated/retired sectors |
| **SMART 187** | Reported Uncorrectable Errors | Count of uncorrectable errors |
| **SMART 188** | Command Timeout | Count of aborted operations due to timeout |
| **SMART 197** | Current Pending Sector Count | Count of "unstable" sectors awaiting remap |
| **SMART 198** | Uncorrectable Sector Count | Count of uncorrectable sectors |

**Key statistics:**
- 4.2% of operational drives had one or more of these five stats > 0
- 76.7% of failed drives had one or more of these five stats > 0
- **23.3% of failed drives showed NO warning from these SMART stats**
- This means nearly 1 in 4 failures are unpredictable from SMART alone

### 4.3 USENIX FAST 2020 Study

**Paper:** "Making Disk Failure Predictions SMARTer!" (Lu et al., 2020, cited 201 times)
**Scope:** 380,000 hard drives (one of the largest studies)

**Key findings:**
- SMART attributes of a randomly selected failed disk do not vary noticeably leading up to failure
- 477 hours before actual failure, SMART signals are still indistinguishable from normal
- Combining SMART with other features (workload patterns, environmental data) improves prediction
- **Implication for recovery decision engine:** SMART data alone is insufficient; recovery decisions must consider many other factors

### 4.4 Additional Predictive SMART Attributes

From various research papers and Backblaze's ML analysis:

| SMART ID | Name | Relevance |
|----------|------|-----------|
| 1 | Read Error Rate | High for some manufacturers |
| 2 | Throughput Performance | Degradation indicates problems |
| 3 | Spin-Up Time | Increasing time indicates mechanical wear |
| 5 | Reallocated Sector Count | **Strong predictor** |
| 7 | Seek Error Rate | High rates indicate mechanical issues |
| 9 | Power-On Hours | Baseline for aging |
| 10 | Spin Retry Count | **Critical** — any non-zero value is concerning |
| 11 | Calibration Retry Count | Indicates servo problems |
| 12 | Power Cycle Count | Context for other attributes |
| 187 | Reported Uncorrectable Errors | **Strong predictor** |
| 188 | Command Timeout | **Strong predictor** |
| 189 | High Fly Writes | Head positioning issues |
| 190 | Temperature Difference | Thermal issues |
| 194 | Temperature | Excessive heat correlates with failure |
| 196 | Reallocation Event Count | **Strong predictor** |
| 197 | Current Pending Sector Count | **Strong predictor** |
| 198 | Uncorrectable Sector Count | **Strong predictor** |
| 199 | CRC Error Count | Interface/cable issues |
| 200 | Multi-Zone Error Rate | Write errors |
| 201 | Soft Read Error Rate | Impending hard errors |
| 240 | Head Flying Hours | Mechanical wear |
| 241 | Total LBAs Written | SSD wear indicator |
| 242 | Total LBAs Read | Usage baseline |
| 249 | NAND Writes (SSD) | SSD endurance |

### 4.5 Feature Engineering Implications for Decision Engine

SMART data provides **one input dimension** to a recovery decision engine, but must be combined with:
- **Filesystem type and state** (ext4, NTFS, APFS, FAT32)
- **Failure mode classification** (logical vs. physical vs. firmware)
- **Disk age and model** (different failure profiles per manufacturer/model)
- **User-reported symptoms** (clicking, not detected, slow, etc.)
- **Recovery attempt history** (what has already been tried)

---

## 5. Partnership Strategies for Data Collection

### 5.1 Repair Shops and Independent Technicians

**Target:** ~30,000+ independent computer repair shops in the US alone

**Value proposition for partners:**
- **Free decision support tool:** They get access to the trained decision engine
- **Case outcome tracking:** They can track their own success rates
- **Community recognition:** Leaderboard of contributors (anonymized)
- **Revenue sharing:** If the engine becomes a paid product, early contributors get free access

**Data collection approach:**
- Build a lightweight data submission tool (mobile-friendly web app)
- Submit case metadata: drive model, failure symptoms, recovery method attempted, outcome
- **No disk images required initially** — just structured case metadata
- Optional: upload anonymized SMART data dumps

**Key partners:**
- **Technibble community:** 200,000+ members, forums for IT professionals
- **iFixit community:** Active repair community
- **Local independent repair shops:** Most receptive to partnerships

### 5.2 Universities with Forensics Programs

**Target programs:**
- Champlain College (Digital Forensics program)
- University of New Haven (Forensic Technology)
- Purdue University (CERIAS)
- Carnegie Mellon (CERT)
- University of Central Florida (Digital Forensics)

**Partnership model:**
- **Research collaboration:** Provide tools and infrastructure; receive anonymized data
- **Student projects:** Students generate test datasets as capstone projects
- **Published research:** Joint papers improve both parties' visibility
- **IRB-approved data collection:** Universities can handle ethical review

**Value for universities:**
- Access to real-world data recovery scenarios
- Publication opportunities
- Student training with cutting-edge tools
- Grant co-application opportunities

### 5.3 Hardware Manufacturers

**Target companies:** Seagate, Western Digital, Samsung, Toshiba, Kingston, Crucial

**Approach:**
- **Failure data sharing:** Manufacturers have RMA data with failure modes
- **Anonymized warranty claim data:** Could reveal failure patterns by model/firmware
- **Test equipment access:** Manufacturers may provide test drives for controlled failure experiments

**Challenges:**
- **Highly protective of failure data** (competitive concern)
- **Legal liability concerns** about sharing customer data
- **NDA requirements** likely

**Strategy:**
- Position as a **failure prevention tool** (benefits the manufacturer)
- Offer to share findings back (improved failure prediction helps them too)
- Start with smaller manufacturers (e.g., SSD controller makers like Phison)

### 5.4 Cloud Providers

**Target:** AWS, Google Cloud, Azure, Backblaze, Wasabi

**What they can provide:**
- **Anonymized failure data** (like Backblaze's Drive Stats)
- **Workload patterns** before failure
- **Recovery success rates** from their own data recovery operations

**Backblaze model (most relevant):**
- They publish their drive stats openly
- Could potentially extend to sharing recovery outcome data
- Already have infrastructure for data collection

**Approach:**
- Partner with Backblaze first (they're already open to sharing data)
- Offer to analyze their data for recovery insights
- Use their published data as a baseline for the decision engine

### 5.5 Other Data Recovery Companies

**Target:** Mid-size and independent recovery firms

**Challenges:**
- The industry is **highly secretive** about techniques and success rates
- Competitive concerns about sharing case data
- No industry consortium for data sharing

**Approach:**
- **Anonymized data sharing:** Create a platform where firms can contribute without revealing competitive information
- **Industry consortium:** Propose a data recovery research consortium
- **Insurance/compliance angle:** Position as a compliance tool (like SOC 2 certification for data recovery)

---

## 6. Data Labeling and Ground Truth

### 6.1 Pre-Corruption Checksums

**The gold standard for synthetic datasets:**

1. Create a disk image with known file set
2. Record SHA-256 checksums of every file
3. Record filesystem metadata (inode numbers, timestamps, directory structure)
4. Apply corruption scenario
5. Attempt recovery
6. Compare recovered files against checksums

**Implementation:**
```bash
# Generate checksums before corruption
find /mnt/test -type f -exec sha256sum {} \; > checksums.txt

# After recovery, verify
sha256sum -c checksums.txt > recovery_results.txt
```

**Metric: Recovery Success Rate (RSR)**
- RSR = (bytes of correctly recovered data) / (total bytes of original data)
- Per-file RSR: binary (file recovered intact or not)
- Partial RSR: percentage of file recovered intact

### 6.2 Known File Sets

**Design a standardized file set for testing:**

| Category | File Types | Count | Total Size |
|----------|-----------|-------|-----------|
| Documents | PDF, DOCX, XLSX, TXT | 500 | 500 MB |
| Images | JPEG, PNG, RAW, HEIC | 1,000 | 5 GB |
| Video | MP4, MOV, AVI | 50 | 10 GB |
| Archives | ZIP, RAR, 7Z | 100 | 1 GB |
| Databases | SQLite, MDB | 20 | 200 MB |
| System | Registry, logs, config | 200 | 100 MB |
| Code | Various source files | 500 | 50 MB |

**Key principle:** Include files that are:
- **Easy to recover** (contiguous, well-known headers)
- **Hard to recover** (fragmented, no headers, small files embedded in MFT)
- **Edge cases** (encrypted, compressed, zero-length, very large)

### 6.3 Comparison with Professional Lab Results

**For real-world cases (not synthetic):**

1. **Dual recovery:** Send the same drive to two different professional labs
2. **Compare outcomes:** File lists, file integrity, recovery methods used
3. **Discrepancy analysis:** Where labs disagree, investigate why
4. **Cost:** This is expensive ($500-$3,000 per case) but provides the highest-quality labels

**Alternative:** Obtain drives that have already been professionally recovered and:
- Compare the recovery tool's output against the professional lab's result
- Use the professional lab's file list as the ground truth

### 6.4 User Confirmation of Recovered Files

**For deployed recovery tools:**

1. After recovery, show users a list of recovered files
2. Ask users to confirm which files are:
   - ✅ Correctly recovered and usable
   - ⚠️ Partially recovered (corrupted but some content accessible)
   - ❌ Incorrectly recovered (wrong file, garbage data)
   - 🤷 Unknown (user can't verify)
3. Use this feedback as **weak labels** for the decision engine
4. Aggregate across many users to build confidence scores

### 6.5 Label Taxonomy for Recovery Scenarios

```
Recovery Outcome:
  - Full recovery (all files intact, checksums match)
  - Partial recovery (some files intact, some corrupted)
  - Metadata recovery (file names/structure recovered but data corrupted)
  - Raw recovery (file signatures found but no names/folders)
  - No recovery (nothing usable)

Failure Mode:
  - Logical (filesystem corruption, no physical damage)
  - Firmware (drive not recognized, wrong capacity)
  - Mechanical (clicking, not spinning, head crash)
  - SSD-specific (TRIM, controller failure, NAND wear)
  - RAID (degraded array, multiple disk failure)

Recovery Method:
  - Software-only (no hardware intervention)
  - Firmware repair (PC-3000, etc.)
  - Head stack replacement
  - PCB swap with donor
  - NAND chip-off
  - RAID reconstruction
```

---

## 7. Privacy and Legal Considerations

### 7.1 Legal Framework

**GDPR (EU):**
- Disk images contain **personal data** by definition (files, emails, browser history, photos)
- Processing requires **legal basis** (consent, legitimate interest, research)
- **Anonymization** removes GDPR obligations, but disk images are extremely difficult to anonymize
- **Pseudonymization** (replacing names with tokens) still leaves data subject to GDPR
- **Right to erasure** (Art. 17): Individuals can request deletion of their data
- **Data minimization** (Art. 5): Collect only what's necessary

**CCPA (California):**
- Similar to GDPR but applies to California residents
- **De-identified data** is excluded from CCPA scope
- Requires that de-identification be "technically robust"

**Key legal question:** Can a disk image ever be truly "anonymized"?

### 7.2 Disk Image Anonymization Challenges

**The fundamental problem:** Disk images contain personal data at every level:
- **File contents:** Documents, emails, photos, videos
- **File metadata:** Names, timestamps, paths
- **Filesystem metadata:** Inode timestamps, directory structures
- **Application data:** Browser history, cookies, registry entries
- **Deleted data:** Unallocated space may contain recoverable PII
- **Slack space:** Partial data in unused sectors

**Existing approaches (from Breitinger et al., 2023, "Sharing datasets for digital forensic: A novel taxonomy and legal concerns"):**
- Unstructured data is especially problematic for privacy as filtering, deleting, or anonymizing information is complex
- Anonymization techniques for disk images are still immature
- The paper proposes a taxonomy for classifying forensic datasets by their privacy sensitivity

### 7.3 Practical Anonymization Techniques

**For synthetic datasets (no privacy concern):**
- Use NPS Test Disk Images (already PII-free, public domain)
- Generate images with only synthetic/generated content
- **This is the recommended approach for most training data**

**For real-world disk images:**

| Technique | Description | Effectiveness |
|-----------|-------------|---------------|
| **File content replacement** | Replace all file contents with synthetic data | High, but destroys filesystem realism |
| **Selective PII scrubbing** | Remove only known PII patterns | Medium — misses unknown PII |
| **Metadata-only preservation** | Keep filesystem structure, replace file contents | Medium — file paths may contain PII |
| **Encryption** | Encrypt image, share only with authorized researchers | High privacy, limits collaboration |
| **Differential privacy** | Add noise to aggregate statistics | Not applicable to disk images |
| **Secure enclaves** | Process images in isolated environments | High privacy, but limits access |

**Recommended approach for real-world cases:**
1. **Never share raw disk images** from real users
2. **Extract only the features needed** for the decision engine:
   - Drive model, capacity, firmware version
   - SMART attributes (no PII)
   - Filesystem type and health metrics
   - Failure mode classification
   - Recovery method and outcome
3. **Store disk images in encrypted, access-controlled environments**
4. **Use synthetic images** for algorithm development and testing

### 7.4 Consent and IRB Framework

**For academic partnerships:**
- University IRB approval required for any human-subjects data
- **Informed consent** from disk owners before their data is used
- **Data use agreements** specifying how data can be shared and used
- **Retention policies** defining how long data is kept

**For commercial data collection:**
- **Terms of service** must clearly state data collection and use
- **Opt-in consent** required (especially under GDPR)
- **Right to withdraw** must be honored
- **Data processing agreements** with any third parties

---

## 8. Dataset Size Estimates

### 8.1 The Class Imbalance Problem

Data recovery scenarios are inherently **imbalanced**:
- **Common scenarios:** Logical corruption, accidental deletion (~80% of cases)
- **Uncommon scenarios:** Firmware failure, RAID degradation (~15%)
- **Rare scenarios:** Head crash, NAND chip-off, SSD TRIM (~5%)

This mirrors the disk failure prediction problem studied by Backblaze and Google:
- Annual failure rate: ~1-2% of drives
- Among failed drives, specific failure modes are even rarer
- **Imbalanced datasets require special ML techniques:** oversampling, SMOTE, cost-sensitive learning

### 8.2 Minimum Viable Dataset Estimates

Based on the disk failure prediction literature and general ML best practices:

| Scenario Type | Minimum Cases | Target Cases | Notes |
|--------------|---------------|--------------|-------|
| Logical corruption (NTFS) | 200 | 1,000 | Most common; need variety of corruption types |
| Logical corruption (ext4) | 200 | 1,000 | |
| Logical corruption (APFS) | 100 | 500 | Less common but growing |
| Accidental deletion | 200 | 1,000 | |
| Bad sectors | 100 | 500 | |
| Firmware failure | 50 | 200 | Harder to collect; synthetic augmentation needed |
| SSD TRIM scenarios | 50 | 200 | |
| RAID degradation | 50 | 200 | |
| Physical damage | 30 | 100 | Most expensive to collect |
| **Total** | **~1,000** | **~5,000** | |

**Minimum viable dataset:** ~1,000 cases with at least 10 different failure mode categories
**Target dataset:** ~5,000 cases with rich feature vectors and labeled outcomes
**Aspirational dataset:** ~50,000+ cases (comparable to Backblaze's scale)

### 8.3 Feature Vector Per Case

Each case in the dataset should include:

| Feature Category | Features | Count |
|-----------------|----------|-------|
| Drive identification | Model, capacity, firmware, age, type (HDD/SSD) | 6 |
| SMART attributes | Key SMART stats (raw + normalized) | 20-40 |
| Filesystem info | Type, size, usage, health status | 5-10 |
| Failure symptoms | User-reported symptoms (encoded) | 5-10 |
| Failure mode | Classification label | 1 |
| Recovery method | What was attempted | 5-10 |
| Recovery outcome | Success rate, file count, data integrity | 3-5 |
| **Total features per case** | | **~50-80** |

### 8.4 Data Augmentation Strategies

To increase effective dataset size without collecting more real cases:

1. **Synthetic scenario generation:** Create 10x variations of each corruption type
2. **Parameter variation:** Vary corruption severity, location, and extent
3. **Filesystem variation:** Same corruption across different filesystems
4. **Cross-validation of failure modes:** Combine multiple failure modes
5. **Transfer learning:** Pre-train on SMART data (plentiful), fine-tune on recovery data (scarce)

---

## 9. The Backblaze Approach

### 9.1 How Backblaze Collects Their Data

**Methodology (from Backblaze blog posts and data documentation):**

1. **Daily SMART data collection:** Every day at Backblaze data centers, a C++ program takes a snapshot of each operational drive
2. **Tool:** They use **Smartmontools** to collect SMART attributes from drives
3. **Additional monitoring:** A tool called **Drive Sentinel** flags read/write errors
4. **Schema:** Each drive record includes:
   - Date
   - Serial number
   - Model number
   - Capacity
   - Failure flag (0 = operational, 1 = failed)
   - Raw and normalized SMART attributes
5. **Failure determination:** A drive is marked as failed when it is:
   - Removed from a storage pod for any reason other than upgrade
   - Or showing persistent errors that require replacement

**Scale:**
- Since 2013, they've collected data on **300,000+ drives**
- Over **3 exabytes** of storage under management
- Data is published quarterly and available for download as CSV files
- The dataset is **open source** and freely available

### 9.2 What Backblaze's Data Includes (and Doesn't)

**Includes:**
- ✅ SMART attributes (daily snapshots)
- ✅ Drive model and capacity
- ✅ Failure/non-failure binary label
- ✅ Operational time before failure

**Does NOT include:**
- ❌ Filesystem type or state
- ❌ Failure mode classification (why did it fail?)
- ❌ Recovery attempt data (they replace, not recover)
- ❌ Recovery outcomes
- ❌ Pre-failure workload patterns
- ❌ Environmental data (temperature, vibration)

### 9.3 Adapting Backblaze's Methodology for Recovery Scenario Collection

**What we can learn from Backblaze's approach:**

| Backblaze Practice | Recovery Scenario Adaptation |
|-------------------|---------------------------|
| Daily SMART snapshots | Collect SMART data at intake of every recovery case |
| Binary failure label | Richer labels: failure mode, recovery method, outcome |
| Open data publication | Publish anonymized recovery case metadata |
| C++ collection program | Build lightweight data collection agent |
| Quarterly reports | Publish quarterly recovery statistics |
| Standardized schema | Define recovery case schema (see Section 8.3) |

**Proposed "Recovery Stats" collection system:**

```
1. Data Collection Agent (lightweight CLI tool)
   - Reads SMART data from incoming drives
   - Records drive model, capacity, firmware
   - Accepts technician input: failure symptoms, recovery method, outcome
   - Anonymizes all data before submission
   - Submits to central database via API

2. Central Database
   - Stores anonymized case data
   - Provides REST API for querying
   - Generates aggregate statistics

3. Open Publication
   - Quarterly reports on recovery statistics
   - Downloadable anonymized dataset
   - Research papers using the data
```

### 9.4 Key Differences from Backblaze

| Factor | Backblaze | Recovery Decision Engine |
|--------|-----------|-------------------------|
| **Data source** | Own data center (homogeneous) | Many sources (heterogeneous) |
| **Failure label** | Binary (failed/working) | Rich (failure mode + recovery outcome) |
| **Scale** | 300K+ drives | Start with 1K-5K cases |
| **Collection cost** | Near-zero (automated) | Moderate (requires technician input) |
| **Privacy concern** | Low (no user data) | High (disk images contain PII) |
| **Time horizon** | 10+ years of data | Start from scratch |

---

## 10. Recommended Dataset Construction Roadmap

### Phase 1: Synthetic Foundation (Months 1-3)
- **Goal:** 1,000 synthetic test cases
- **Approach:** Generate disk images with known file sets, apply scripted corruption
- **Deliverable:** Labeled dataset with 100% ground truth
- **Cost:** Low (compute time only)

### Phase 2: Metadata Collection (Months 3-6)
- **Goal:** 5,000 case metadata records (no disk images)
- **Approach:** Partner with 10-20 repair shops; collect structured case data
- **Deliverable:** Decision engine trained on symptoms + outcomes
- **Cost:** Low (tool development + partner onboarding)

### Phase 3: Enriched Data Collection (Months 6-12)
- **Goal:** 2,000 cases with SMART data + outcomes
- **Approach:** Build data collection agent; distribute to partners
- **Deliverable:** Enhanced decision engine with SMART features
- **Cost:** Moderate (tool development, partner incentives)

### Phase 4: Academic Partnership (Months 6-18)
- **Goal:** 5,000 additional cases from university forensics programs
- **Approach:** Research collaboration with 3-5 universities
- **Deliverable:** Published research, validated decision engine
- **Cost:** Moderate (research grants, shared infrastructure)

### Phase 5: Open Dataset Publication (Months 12-24)
- **Goal:** Publish the first open dataset for data recovery research
- **Approach:** Following Backblaze's model — quarterly releases
- **Deliverable:** Community resource, citation magnet, competitive moat
- **Cost:** Low (infrastructure already built)

---

## 11. Key References

1. **Pinheiro et al. (2007)** — "Failure Trends in a Large Disk Drive Population" — FAST '07. [Google Research](https://research.google.com/archive/disk_failures.pdf) — Cited 1,268 times
2. **Lu et al. (2020)** — "Making Disk Failure Predictions SMARTer!" — USENIX FAST '20. Cited 201 times
3. **Grajeda et al. (2017)** — "Availability of datasets for digital forensics – And what is missing" — DFRWS '17. Cited 191 times
4. **Breitinger et al. (2023)** — "Sharing datasets for digital forensic: A novel taxonomy and legal concerns" — Cited 32 times
5. **Backblaze Blog** — "What SMART Stats Tell Us About Hard Drives" (2016) — https://www.backblaze.com/blog/what-smart-stats-indicate-hard-drive-failures
6. **Backblaze Blog** — "Using Machine Learning to Predict Hard Drive Failures" (2021) — https://www.backblaze.com/blog/using-machine-learning-to-predict-hard-drive-failures
7. **Backblaze Drive Stats Data** — https://www.backblaze.com/cloud-storage/resources/hard-drive-test-data
8. **NIST CFReDS** — https://cfreds.nist.gov
9. **Digital Corpora** — https://digitalcorpora.org/corpora/disk-images
10. **Elcomsoft Blog** — "What TRIM, DRAT, and DZAT Really Mean for SSD Forensics" (2025) — https://blog.elcomsoft.com/2025/06/what-trim-drat-and-dzat-really-mean-for-ssd-forensics
11. **Tomer et al. (2021)** — "Hard disk drive failure prediction using SMART attribute" — ScienceDirect. Cited 28 times
12. **Tomer et al. (2022)** — "Predicting severely imbalanced data disk drive failures with machine learning" — ScienceDirect. Cited 28 times

---

## 12. Summary of Key Findings

| Area | Key Finding | Implication |
|------|-------------|-------------|
| **Existing datasets** | No public datasets for damaged/corrupted disk recovery | Must build from scratch; synthetic data is essential |
| **Professional lab knowledge** | Tacit, proprietary, craft-based | Must codify through structured case collection |
| **Disk image generation** | Feasible with existing tools (dd, dmsetup, qemu-img) | Can generate 1,000+ synthetic cases quickly |
| **SMART attributes** | 5 key attributes predict 76.7% of failures; 23.3% unpredictable | SMART is necessary but not sufficient; combine with other features |
| **Partnerships** | Repair shops are most accessible; Backblaze is most open | Start with repair shops + Backblaze data; approach universities for research |
| **Ground truth** | Pre-corruption checksums are gold standard for synthetic data | Synthetic data provides the strongest labels; real-world labels are weaker |
| **Privacy** | Disk images are extremely difficult to anonymize | Collect only metadata features; never share raw images |
| **Dataset size** | Minimum 1,000 cases; target 5,000; aspirational 50,000+ | Start with synthetic; grow through partnerships |
| **Backblaze model** | Automated daily collection, open publication, quarterly reports | Adapt their methodology for recovery case metadata |
