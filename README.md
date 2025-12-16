# gexport

**Makefile-like export tool for GIMP**

Write a simple YAML file that tells `gexport` how to export, scale and crop
multiple images from your complex GIMP projects.

![gexport exporting multiple images from a complex GIMP project using a YAML schema](.github/gexport-diagram.webp)

## Install

```shell
$ git clone https://github.com/petersuttondev/gexport.git
$ cd gexport
$ pip install .
```

## Get Started

```shell
$ cd /path/to/project
$ gexport json-schema > gexport-schema.json
```

Create an empty gexport YAML file

```yaml
# yaml-language-server: $schema=./gexport-schema.json
database: gexport.sqlite3
xcfs: {}
```

Add GIMP projects:

```yaml
# yaml-language-server: $schema=./gexport-schema.json
database: gexport.sqlite3
xcfs:
    project-a.xcf:
        exports:
            project-a.png: {}
    project-b.xcf:
        exports:
            project-b.png: {}
```

Export images:

```shell
$ gexport export
$ ls *.png
project-a.png project-b.png
```

Now check out the example directory.

## Documentation

```yaml
# yaml-language-server: $schema=./gexport-schema.json
database: gexport.sqlite3
xcfs:
    # Path to your .xcf file, relative to this file
    project-a.xcf:
        exports:
            # Export path, relative to this file.
            image-a.png: {}

            # Show all layers
            image-b.png:
                default: show
                
            # Hide by default and show one layer
            image-c.png:
                default: hide
                show: Layer A

            # Show multiple layers
            image-d.png
                default: hide
                show:
                    - Layer A
                    - Layer B

            # Show all layers in a group
            image-e.png:
                default: hide
                show:
                    group: Group A
                    default: show

            # Show some layers in a group
            image-f.png:
                default: hide
                show:
                    group: Group A
                    show:
                        - Layer A
                        - Layer B
```

