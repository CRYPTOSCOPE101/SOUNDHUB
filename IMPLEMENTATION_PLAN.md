# Implementation Plan: Integrate Universal Artifact Store with Ableton Project Version Workflow

## Overview
This plan outlines how to integrate the newly implemented Universal Artifact Store with the existing Ableton project version workflow in SoundHub. The goal is to allow project versions (with their .als/.alp files, audio exports, stems, and metadata) to be discoverable and purchasable through the Universal Artifact Store marketplace.

## Current State Analysis

### Project Version Workflow (Existing)
1. **Project** → owns → **Commits** (Git snapshots)
2. **Commit** → contains → **FileSnapshots** (includes .als/.alp project files)
3. **ReviewSession** → belongs to → **Project** (nullable)
4. **ReviewVersion** → belongs to → **ReviewSession** and links to → **Commit** (via commit_id)
   - Contains rendered audio blob (blob_sha)
5. **StemAsset** → belongs to → **ReviewVersion** (individual stems)
6. **ReleasePackage** → belongs to → **ReviewSession** and links to → approved **ReviewVersion**
7. **Deliverable** → belongs to → **ReleasePackage**
   - Already contains: blob_sha (file content), format, source_version_id (→ ReviewVersion), audio metadata
   - Missing: marketplace fields (license, price, etc.)

### Universal Artifact Store (Recent Implementation)
- Deals with **Package** model (marketplace assets like sample packs, presets)
- Provides public catalog API with filtering (BPM, genre, format, key, etc.)
- Secure token-based downloads (HMAC-SHA256)
- Recommendation system (scoring algorithm)
- License receipt generation
- API endpoint: `GET /api/assets`

## Integration Strategy

Extend the **Deliverable** model to support marketplace distribution, then modify the Universal Artifact Store to include marketplace deliverables alongside Packages.

### Why Deliverable (not Package)?
1. **Already linked to version**: Deliverable.source_version_id → ReviewVersion
2. **Already contains audio blob**: Deliverable.blob_sha
3. **Already has metadata**: format, sample_rate, bit_depth, etc.
4. **Natural extension**: Deliverables represent the "products" of a project version
5. **Minimal duplication**: Avoids duplicating blob storage (both Package and Deliverable would reference same blob_sha)

## Implementation Steps

### 1. Extend Deliverable Model for Marketplace Support
**File**: `backend/app/models.py`
**Location**: `Deliverable` class (around line 531)

Add marketplace fields:
```python
# Marketplace fields
license: Mapped[str | None] = mapped_column(String(64), nullable=True)
price_cents: Mapped[int] = mapped_column(Integer, default=0)
verified: Mapped[bool] = mapped_column(default=False)
bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
key: Mapped[str | None] = mapped_column(String(32), nullable=True)
genre: Mapped[str | None] = mapped_column(String(128), nullable=True)
tags: Mapped[str | None] = mapped_column(Text, default="")
```

### 2. Modify Assets Endpoint to Include Marketplace Deliverables
**File**: `backend/app/routers/assets.py`
**Function**: `list_assets` (around line 20)

Changes:
- Query both `Package` and `Deliverable` tables
- For Deliverables: filter where `license IS NOT NULL` (marketplace available)
- Apply filters to both tables with appropriate field mappings
- Combine/format results to match identical API response structure
- Handle sorting and pagination across both result sets

### 3. Field Mapping for Filtering
Map API parameters to model fields:

| API Parameter | Package Field | Deliverable Field | Notes |
|---------------|---------------|-------------------|-------|
| bpm_min/bmp_max | bpm | bpm | Direct mapping |
| license | license | license | Case-insensitive search |
| format | format | format | Exact match |
| key | key | key | Case-insensitive search |
| genre | genre | genre | Substring matching (comma-separated) |
| plugin | devices | [TBD] | May need Project metadata or leave Package-only |
| q (text search) | name/description | filename/tags | May need to add description field to Deliverable |

### 4. Response Format Mapping
Ensure identical JSON structure for both Package and Deliverable results:

```json
{
  "listing_id": "<id>",
  "name": "<name>",
  "description": "<description>",
  "license": "<license>",
  "verified": <boolean>,
  "bpm": [<number>] or null,
  "genre": "<genre>",
  "devices": "<devices>",
  "plugins": "<devices>",  // For test compatibility
  "format": "<format>",
  "key": "<key>",
  "duration_seconds": <number>,
  "waveform": [<float> * 100]
}
```

For Deliverable mapping:
- `listing_id` → `deliverable.id`
- `name` → `deliverable.filename` (or add name field)
- `description` → `deliverable.tags` (or add description field)
- `license` → `deliverable.license`
- `verified` → `deliverable.verified`
- `bpm` → `[deliverable.bpm]` if not None else `null`
- `genre` → `deliverable.genre`
- `devices` → "" (empty string, or derive from Project metadata)
- `plugins` → same as devices (for compatibility)
- `format` → `deliverable.format`
- `key` → `deliverable.key`
- `duration_seconds` → placeholder or derive from audio analysis
- `waveform` → `[0.5] * 100` (placeholder)

### 5. Download Endpoints Compatibility
Ensure download endpoints work for Deliverable-based marketplace items:
- `GET /api/assets/{id}/download` 
- `GET /api/assets/{id}/download64`

These currently use `catalog.find_asset(db, asset_id)` which only looks at Package model.
Need to extend to also find Deliverables by ID when Package not found.

### 6. License Receipt Compatibility
Ensure `POST /api/assets/{id}/receipt` works for Deliverable items:
- Currently uses `catalog.find_asset(db, asset_id)` → Package only
- Needs to also handle Deliverables
- Receipt generation logic in `services/licenses.py` is generic and should work

### 7. Recommendations Endpoint
Ensure `GET /api/assets/recommend` works with Deliverables:
- Currently queries Package model only
- Needs to also include marketplace Deliverables
- Scoring algorithm should work with Deliverable fields

## Technical Details

### Database Migration
Add new columns to `release_deliverables` table:
- `license` VARCHAR(64) NULL
- `price_cents` INTEGER NOT NULL DEFAULT 0
- `verified` BOOLEAN NOT NULL DEFAULT FALSE
- `bpm` INTEGER NULL
- `key` VARCHAR(32) NULL
- `genre` VARCHAR(128) NULL
- `tags` TEXT NULL DEFAULT ''

### Security Considerations
1. **Marketplace Visibility**: Only Deliverables with `license IS NOT NULL` appear in marketplace
2. **Ownership Validation**: Ensure users can only mark their own deliverables for marketplace
3. **Download Authorization**: Existing token validation (HMAC-SHA256) applies to both Packages and Deliverables
4. **Rate Limiting**: Consider adding marketplace-specific rate limits if needed

### Backward Compatibility
- All existing Package-based marketplace functionality continues unchanged
- All existing project/workflow functionality continues unchanged
- New fields are nullable with safe defaults
- No breaking API changes

## Implementation Sequence

### Phase 1: Model and Database Changes
1. Add marketplace fields to Deliverable model
2. Create and apply database migration
3. Verify schema update

### Phase 2: API Endpoint Updates
1. Modify `list_assets` to query both Package and Deliverable
2. Implement field mapping and filtering logic
3. Test basic catalog functionality
4. Update download endpoints to handle both Package and Deliverable IDs
5. Update license receipt endpoint to handle both types
6. Update recommendations endpoint to include Deliverables

### Phase 3: Testing and Verification
1. Verify all existing API tests still pass
2. Create test data with marketplace Deliverables
3. Test filtering, search, sorting across both content types
4. Test secure download for Deliverable-based marketplace items
5. Test license receipt generation for Deliverables
6. Test recommendations include Deliverables with proper scoring
7. Verify metadata linking (Deliverable → ReviewVersion → Commit → FileSnapshot)

### Phase 4: Optional Enhancements
1. Add name/description fields to Deliverable if needed for better marketplace presentation
2. Consider adding UI/admin interfaces to mark deliverables as marketplace items
3. Add analytics for marketplace deliverable views/purchases

## Artifact Linking Verification

When a user purchases a Deliverable from the marketplace, they should be able to verify:
1. **Audio File**: Get via secure download endpoint (Deliverable.blob_sha)
2. **Project File**: 
   - Deliverable.source_version_id → ReviewVersion
   - ReviewVersion.commit_id → Commit
   - Commit.filesnapshot where path ends in .als or .alp
3. **Stems**: 
   - StemAsset where version_id = ReviewVersion.id
4. **Metadata**: 
   - Deliverable fields (format, sample_rate, bit_depth, etc.)
   - ReviewVersion metadata (duration_s, audio_format, watermark_sha)
   - Commit metadata (author, timestamp, message)
5. **Provenance**: Immutable chain from Deliverable → ReviewVersion → Commit → FileSnapshots

This provides complete traceability from marketplace purchase back to the originating project version and files.

## Estimated Effort
- Model changes: Low
- Database migration: Low
- API endpoint modifications: Medium (due to dual-query logic and field mapping)
- Testing: Medium
- Total: Approximately 1-2 days of development time

## Risks and Mitigations
1. **Performance Impact**: Querying two tables instead of one
   - Mitigation: Ensure proper indexing on filtered/additional fields
   - Mitigation: Consider caching strategies if needed
2. **API Response Consistency**: Ensuring identical structure
   - Mitigation: Create helper functions to convert both models to common format
   - Mitigation: Comprehensive testing of edge cases
3. **Security**: Accidentally exposing non-marketplace deliverables
   - Mitigation: Strict filtering (license IS NOT NULL)
   - Mitigation: Authorization checks on modify endpoints
4. **Data Duplication**: Storing same metadata in multiple places
   - Mitigation: Deliverable already contains necessary audio metadata
   - Mitigation: Marketplace fields are minimal additions

## Open Questions for Review
1. Should Deliverable gain a `name` field separate from `filename` for better marketplace presentation?
2. Should Deliverable gain a `description` field for richer marketplace content?
3. How should the `plugin` filter work for Deliverables? (Possibly look at Project metadata or leave as Package-only feature)
4. Should we add a `is_marketplace_item` boolean instead of relying on `license IS NOT NULL`?
5. Should marketplace Deliverables have a different purchasing flow than Packages?

Please review this plan and provide feedback or approval before implementation begins.