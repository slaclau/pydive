project('io.github.slaclau.pydive',
  version: run_command(['python', '-m', 'setuptools_scm'], check: true).stdout().strip(),
  meson_version: '>=1.1'
)

python = import('python')
i18n = import('i18n')
if target_machine.system() != 'darwin'
  gnome = import('gnome')
endif
subdir('src')
subdir('data')

if target_machine.system() != 'darwin'
  gnome.post_install(
     glib_compile_schemas: false,
    gtk_update_icon_cache: false,
  update_desktop_database: false,
  )
endif