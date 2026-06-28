# Score Trans Domain

Score Trans converts score source material into an editable Jianpu workspace and paginated render output.

## Language

**Score Workspace**:
The in-memory editing state for one or more source pages, their Jianpu text, history identity, and render output.
_Avoid_: Task state, temporary page state

**Source Page**:
One uploaded or PDF-derived page that may produce MusicXML and Jianpu text.
_Avoid_: Render page, history page

**Recognition Batch**:
An ordered group of Source Pages recognized and edited as one score.
_Avoid_: Task batch

**Render Page**:
One paginated SVG page produced from the current Jianpu text, which may span multiple Source Pages.
_Avoid_: Source page

**History Page**:
The persisted record corresponding to one Source Page within a Recognition Batch.
_Avoid_: Render page

## Relationships

- A **Recognition Batch** contains one or more **Source Pages**
- A **Score Workspace** holds one active **Recognition Batch**
- A **Source Page** may have one **History Page**
- A **Recognition Batch** produces one or more **Render Pages**

## Example dialogue

> **Dev:** “Does the second Render Page belong to the second Source Page?”
> **Domain expert:** “Not necessarily — Render Pages are repaginated from the whole Recognition Batch.”

## Flagged ambiguities

- “page” previously meant Source Page, History Page, and Render Page; use the qualified terms above.
