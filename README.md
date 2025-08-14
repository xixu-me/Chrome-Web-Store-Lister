# Chrome Web Store Lister

[![List Update](https://github.com/xixu-me/Chrome-Web-Store-Lister/actions/workflows/main.yml/badge.svg)](https://github.com/xixu-me/Chrome-Web-Store-Lister/actions/workflows/main.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)

An automated Chrome Web Store item data collection system. This repository automatically collects and catalogs all publicly available Chrome Web Store items daily.

## How to Use

### Get Data

#### Download from Releases

- **Latest Data**: [Download data.json](https://github.com/xixu-me/Chrome-Web-Store-Lister/releases/latest/download/data.json)
- **Historical Data**: Browse [all releases](https://github.com/xixu-me/Chrome-Web-Store-Lister/releases) by date

#### Direct API Access

```bash
# Download latest data
curl -L https://github.com/xixu-me/Chrome-Web-Store-Lister/releases/latest/download/data.json
```

### Data Format

The data is provided as a JSON array containing Chrome Web Store items:

```json
[
  {
    "id": "ajiejgobfcifcikbahpijopolfjoodgf",
    "name": "Xget Now",
    "page": "https://chromewebstore.google.com/detail/xget-now/ajiejgobfcifcikbahpijopolfjoodgf",
    "file": "https://clients2.google.com/service/update2/crx?response=redirect&prodversion=138&acceptformat=crx2,crx3&x=id%3Dajiejgobfcifcikbahpijopolfjoodgf%26uc"
  }
]
```

### Integration Examples

#### Python

```python
import requests

# Fetch latest data
response = requests.get(
    "https://github.com/xixu-me/Chrome-Web-Store-Lister/releases/latest/download/data.json"
)
items = response.json()
print(f"Total items: {len(items)}")
```

#### JavaScript

```javascript
// Fetch latest data
fetch('https://github.com/xixu-me/Chrome-Web-Store-Lister/releases/latest/download/data.json')
  .then(response => response.json())
  .then(items => {
    console.log(`Total items: ${items.length}`);
  });
```

## Disclaimer

This repository is provided for educational and research purposes only. Users are responsible for complying with Google's Terms of Service and the Chrome Web Store's policies. The authors are not responsible for any misuse of this repository or any consequences resulting from its use. Please use responsibly and respect rate limits and website policies.

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) file.
