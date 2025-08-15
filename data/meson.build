pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

if target_machine.system() != 'darwin'
if get_option('wheel')
  gnome.compile_resources('resources',
    'resources.gresource.xml',
    gresource_bundle: true,
    install: true,
    install_dir: pkgdatadir,
  )
else
  gnome.compile_resources('resources',
    'resources.gresource.xml',
    gresource_bundle: true,
    install: true,
    install_dir: py_installation.get_install_dir() / 'pydive' / 'data',
  )
endif
endif