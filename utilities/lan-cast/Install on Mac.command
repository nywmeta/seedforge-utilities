#!/bin/zsh
lan_cast_folder=${0:A:h}
python3 "$lan_cast_folder/helper/install.py" --interactive
lan_cast_result=$?
echo
if [ "$lan_cast_result" -ne 0 ]; then
  echo "Setup did not complete. See the message above or follow README.md."
fi
read "lan_cast_close?Press Return to close. "
exit "$lan_cast_result"
