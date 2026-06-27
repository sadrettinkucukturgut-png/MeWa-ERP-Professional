# MeWa ERP Professional - Development Rules

## General Rules
- Never rewrite working files.
- Only modify the requested modules.
- Reuse existing code whenever possible.
- Follow the existing project architecture.
- Avoid code duplication.

## UI Standard
Every module must include:
- Toolbar
- Search
- Statistics Cards
- Table
- Right Click Menu
- Double Click Edit
- Excel Export
- PDF Export
- Print
- WhatsApp
- Email
- Website
- Column Visibility

## Toolbar Order
1. New
2. Excel
3. PDF
4. Print
5. WhatsApp
6. Email
7. Website
8. Column Visibility

## Dialog Standard
- Large dialogs must use QScrollArea.
- Mouse wheel scrolling must work.

## Currency Standard
- Every money field must include a currency selector.
- Default currency: USD.

## Export Standard
- Use shared services.
- Never duplicate export code.

## CRUD Standard
- Reuse the Base CRUD architecture.

## Design
- Use the MeWa Automotive logo.
- Use the same design language across all modules.
- Never remove existing working functionality.
