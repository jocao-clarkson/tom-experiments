# logship

Collects device logs into timestamped bundles and ships them to the support bucket.

```
logship bundle /var/log/app/*.log   # create bundle-<UTC timestamp>.tar.gz
logship list                        # show local bundles and upload state
logship --json list                 # machine-readable
```

Bundles live in `~/.local/share/logship/bundles` unless `bundle_dir` is set in
`~/.config/logship/config.toml` or `LOGSHIP_BUNDLE_DIR` is exported. An uploaded
bundle has a sibling `<name>.uploaded` marker file.

## Development

```
pip install -e '.[dev]'
pytest
```
