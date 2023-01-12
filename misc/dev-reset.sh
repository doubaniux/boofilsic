#!/bin/sh
# Reset databases and migrations, for development only

[ -f manage.py ] || exit $1

echo "\033[0;31mWARNING: this script will destroy all neodb databases and migrations"
while true; do
    read -p "Do you wish to continue? (yes/no) " yn
    case $yn in
        [Yy]* ) break;;
        [Nn]* ) exit;;
    esac
done

psql $* postgres -c "DROP DATABASE IF EXISTS neodb;" || exit $?

psql $* postgres -c "DROP DATABASE IF EXISTS test_neodb;" || exit $?

psql $* postgres -c "CREATE DATABASE neodb ENCODING 'UTF8' LC_COLLATE='en_US.UTF-8' LC_CTYPE='en_US.UTF-8' TEMPLATE template0;" || exit $?

find -type d -name migrations | xargs rm -rf

python3 manage.py makemigrations mastodon users management common  catalog journal social legacy

python3 manage.py migrate || exit $?

psql $* neodb -c "CREATE DATABASE test_neodb WITH TEMPLATE neodb;" || exit $?

python3 manage.py check
