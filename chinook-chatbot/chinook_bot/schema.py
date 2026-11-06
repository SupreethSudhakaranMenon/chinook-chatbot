"""Chinook schema card used as the model's only map of the world."""

from __future__ import annotations

TABLES: dict[str, dict] = {
    "Album": {
        "columns": {
            "AlbumId": "INTEGER PK",
            "Title": "NVARCHAR(160) NOT NULL",
            "ArtistId": "INTEGER NOT NULL FK -> Artist.ArtistId",
        },
        "pk": ["AlbumId"],
    },
    "Artist": {
        "columns": {
            "ArtistId": "INTEGER PK",
            "Name": "NVARCHAR(120)",
        },
        "pk": ["ArtistId"],
    },
    "Customer": {
        "columns": {
            "CustomerId": "INTEGER PK",
            "FirstName": "NVARCHAR(40) NOT NULL",
            "LastName": "NVARCHAR(20) NOT NULL",
            "Company": "NVARCHAR(80)",
            "Address": "NVARCHAR(70)",
            "City": "NVARCHAR(40)",
            "State": "NVARCHAR(40)",
            "Country": "NVARCHAR(40)",
            "PostalCode": "NVARCHAR(10)",
            "Phone": "NVARCHAR(24)",
            "Fax": "NVARCHAR(24)",
            "Email": "NVARCHAR(60) NOT NULL",
            "SupportRepId": "INTEGER FK -> Employee.EmployeeId",
        },
        "pk": ["CustomerId"],
    },
    "Employee": {
        "columns": {
            "EmployeeId": "INTEGER PK",
            "LastName": "NVARCHAR(20) NOT NULL",
            "FirstName": "NVARCHAR(20) NOT NULL",
            "Title": "NVARCHAR(30)",
            "ReportsTo": "INTEGER FK -> Employee.EmployeeId",
            "BirthDate": "DATETIME",
            "HireDate": "DATETIME",
            "Address": "NVARCHAR(70)",
            "City": "NVARCHAR(40)",
            "State": "NVARCHAR(40)",
            "Country": "NVARCHAR(40)",
            "PostalCode": "NVARCHAR(10)",
            "Phone": "NVARCHAR(24)",
            "Fax": "NVARCHAR(24)",
            "Email": "NVARCHAR(60)",
        },
        "pk": ["EmployeeId"],
    },
    "Genre": {
        "columns": {
            "GenreId": "INTEGER PK",
            "Name": "NVARCHAR(120)",
        },
        "pk": ["GenreId"],
    },
    "Invoice": {
        "columns": {
            "InvoiceId": "INTEGER PK",
            "CustomerId": "INTEGER NOT NULL FK -> Customer.CustomerId",
            "InvoiceDate": "DATETIME NOT NULL",
            "BillingAddress": "NVARCHAR(70)",
            "BillingCity": "NVARCHAR(40)",
            "BillingState": "NVARCHAR(40)",
            "BillingCountry": "NVARCHAR(40)",
            "BillingPostalCode": "NVARCHAR(10)",
            "Total": "NUMERIC(10,2) NOT NULL",
        },
        "pk": ["InvoiceId"],
    },
    "InvoiceLine": {
        "columns": {
            "InvoiceLineId": "INTEGER PK",
            "InvoiceId": "INTEGER NOT NULL FK -> Invoice.InvoiceId",
            "TrackId": "INTEGER NOT NULL FK -> Track.TrackId",
            "UnitPrice": "NUMERIC(10,2) NOT NULL",
            "Quantity": "INTEGER NOT NULL",
        },
        "pk": ["InvoiceLineId"],
    },
    "MediaType": {
        "columns": {
            "MediaTypeId": "INTEGER PK",
            "Name": "NVARCHAR(120)",
        },
        "pk": ["MediaTypeId"],
    },
    "Playlist": {
        "columns": {
            "PlaylistId": "INTEGER PK",
            "Name": "NVARCHAR(120)",
        },
        "pk": ["PlaylistId"],
    },
    "PlaylistTrack": {
        "columns": {
            "PlaylistId": "INTEGER NOT NULL FK -> Playlist.PlaylistId (composite PK)",
            "TrackId": "INTEGER NOT NULL FK -> Track.TrackId (composite PK)",
        },
        "pk": ["PlaylistId", "TrackId"],
    },
    "Track": {
        "columns": {
            "TrackId": "INTEGER PK",
            "Name": "NVARCHAR(200) NOT NULL",
            "AlbumId": "INTEGER FK -> Album.AlbumId",
            "MediaTypeId": "INTEGER NOT NULL FK -> MediaType.MediaTypeId",
            "GenreId": "INTEGER FK -> Genre.GenreId",
            "Composer": "NVARCHAR(220)",
            "Milliseconds": "INTEGER NOT NULL",
            "Bytes": "INTEGER",
            "UnitPrice": "NUMERIC(10,2) NOT NULL",
        },
        "pk": ["TrackId"],
    },
}

FOREIGN_KEYS = [
    "Album.ArtistId -> Artist.ArtistId (FK_Artist_Album)",
    "Track.AlbumId -> Album.AlbumId (FK_Album_Track)",
    "Track.MediaTypeId -> MediaType.MediaTypeId (FK_MediaType_Track)",
    "Track.GenreId -> Genre.GenreId (FK_Genre_Track)",
    "PlaylistTrack.PlaylistId -> Playlist.PlaylistId (FK_Playlist_PlaylistTrack)",
    "PlaylistTrack.TrackId -> Track.TrackId (FK_Track_PlaylistTrack)",
    "InvoiceLine.TrackId -> Track.TrackId (FK_Track_InvoiceLine)",
    "InvoiceLine.InvoiceId -> Invoice.InvoiceId (FK_Invoice_InvoiceLine)",
    "Invoice.CustomerId -> Customer.CustomerId (FK_Customer_Invoice)",
    "Customer.SupportRepId -> Employee.EmployeeId (FK_Employee_Customer)",
    "Employee.ReportsTo -> Employee.EmployeeId (FK_Employee_ReportsTo)",
]

ALLOWED_TABLES = {name.lower(): name for name in TABLES}
ALLOWED_TABLES["chinook_fts"] = "chinook_fts"

ALLOWED_COLUMNS: dict[str, set[str]] = {
    name.lower(): {col.lower() for col in spec["columns"]} for name, spec in TABLES.items()
}
ALLOWED_COLUMNS["chinook_fts"] = {
    "entity_type",
    "entity_id",
    "name",
    "extra",
    "rank",
}

NOTES = """
This is a sample digital media store (Chinook). Employee and customer rows are fictitious.
Sales cover a multi-year period of invoices. Treat this database as the only source of truth.
Join paths:
- Catalog: Artist -> Album -> Track -> Genre / MediaType
- Playlists: Playlist -> PlaylistTrack -> Track
- Sales: Customer -> Invoice -> InvoiceLine -> Track
- Support: Employee <- Customer.SupportRepId
Revenue for a track/artist is SUM(InvoiceLine.UnitPrice * InvoiceLine.Quantity), not Track.UnitPrice alone.
Invoice.Total is the invoice header amount.
"""


def schema_card() -> str:
    lines = ["Chinook SQLite schema (only these tables exist):", ""]
    for table, spec in TABLES.items():
        lines.append(f"TABLE {table}")
        for col, desc in spec["columns"].items():
            lines.append(f"  - {col}: {desc}")
        lines.append("")
    lines.append("Foreign keys:")
    for fk in FOREIGN_KEYS:
        lines.append(f"  - {fk}")
    lines.append(NOTES)
    return "\n".join(lines)
