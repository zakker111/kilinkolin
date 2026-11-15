"""Feed adapters: one module per source, each exposing fetch().

An adapter never raises past its own boundary — a broken source must not blank the site.
Rows from a source are real: do not mark them sample.
"""
