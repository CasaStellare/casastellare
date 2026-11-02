# Casa Stellare

Static copy of [casastellare.com](https://casastellare.com), without WordPress or Elementor.

The pages, captions, and web images live in this folder. Print masters (TIFFs and PSDs, about 6 GB) stay in the photo archive and are not part of the site.

## Preview

```bash
python3 -m http.server 8080
```

Open http://localhost:8080

## Refresh from the live site

```bash
python3 scripts/sync.py
```

That downloads the public pages and media library, writes `content/site.json`, and rebuilds the HTML. Edit `content/site.json` and run the script again after a pull, or edit the HTML directly and skip the rebuild.

## What this copy does not include

- WordPress users, comments, and the database
- WooCommerce orders. The shop currently has no products.
- Elementor editor data. The rendered pages and images are what got pulled.
- The TIFF masters

A full WordPress backup (database plus `wp-content`) still has to come from the host or from Tools → Export in wp-admin. Use that if you need drafts or order history. This folder is the site you can host as static files.
