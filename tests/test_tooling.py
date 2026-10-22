def test_dependencies_and_scripts_import():
    import mutagen, yaml, nextrack_tags
    assert mutagen.version >= (1, 47)
    assert yaml.__version__ >= "6.0"
    assert callable(nextrack_tags.main)
