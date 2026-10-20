CC = gcc
FLEX = flex
YACC = yacc
CFLAGS = -Wall -Wextra -g

# Apple's /usr/bin wrappers can require full Xcode even when these tools exist.
ifeq ($(shell uname -s),Darwin)
ifneq ($(wildcard /Library/Developer/CommandLineTools/usr/bin/bison),)
YACC = /Library/Developer/CommandLineTools/usr/bin/bison -y
FLEX = /Library/Developer/CommandLineTools/usr/bin/flex
endif
endif

all: mini_compiler

y.tab.c: parser.y
	$(YACC) -d parser.y

y.tab.h: y.tab.c


lex.yy.c: lexer.l y.tab.h
	$(FLEX) -o lex.yy.c lexer.l

mini_compiler: y.tab.c lex.yy.c common.c dot.c main.c common.h
	$(CC) $(CFLAGS) -o mini_compiler y.tab.c lex.yy.c common.c dot.c main.c -lm

clean:
	rm -f mini_compiler y.tab.c y.tab.h lex.yy.c ast.dot ast.png tac.txt optimized_tac.txt symbols.tsv

run: mini_compiler
	./mini_compiler example.src

.PHONY: all clean run
