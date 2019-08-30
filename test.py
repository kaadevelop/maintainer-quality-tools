import re

commit = 'sdfsd dfd'



first_word = commit.split(' ', 1)[0]
if first_word == 'Revert':
    print('yes!')
