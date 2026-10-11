#!/bin/zsh
lan_cast_folder=${0:A:h}
python3 -B "$lan_cast_folder/helper/companion.py" --open
lan_cast_result=$?
if [ "$lan_cast_result" -ne 0 ]; then
  read "lan_cast_close?Press Return to close. "
fi
exit "$lan_cast_result"
