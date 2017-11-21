# Kattis CLI
Kattis online judge command line tool written in Python.  Runs both in Python 2 and in Python 3.

# Configuration file

Before running the submission client, you need to [download a configuration file](https://open.kattis.com/download/kattisrc). This file includes a secret personal token that allows you to log in. It should be placed in your home directory, or in the same directory as `submit.py`, and be called `.kattisrc`.

# Running the client

The easiest way to use the client is if you have named your source code to *problemid*.suffix, where suffix is something suitable for the language (e.g., `.java` for Java, `.c` for C, `.cc` or `.cpp` for C++, `.py` for Python, `.cs` for C#, `.go` for Go, and so on...).

Let's assume you're solving the problem [Hello World!](https://open.kattis.com/problems/hello) (with problem id `hello`) and that your java solution is in the file `Hello.java`. Then you can simply run `submit.py Hello.java`, and the client will make the correct guesses. You will always be prompted before a submission is sent.

**Note:** If you get an error message like this: `ModuleNotFoundError: No module named 'requests'` when you run `submit.py` it's because the module 'requests' isn't installed. To install the module, check out [this](https://stackoverflow.com/a/17309309/4132739) StackOverflow answer. 

# More advanced options

The submit client can handle multiple files in a submission. For such submissions, the filename and suffix of the first file listed on the command line is the basis of the guesses. It is ok to list a file multiple times, e.g., `submit.py Hello.java *.java` will work as intended.

In case the client guesses wrong, you can correct it by specifying a command line option. Running `submit.py -h` will list all options. The options are:

* `-p <problem_id>`: overrides problem guess
* `-m <mainclass>`: overrides mainclass guess
* `-l <language>`: overrides language guess
* `-f`: forces submission (i.e., no prompt)
