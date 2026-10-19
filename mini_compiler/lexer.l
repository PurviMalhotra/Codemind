%{
#include "common.h"
#include "y.tab.h"
#include <stdlib.h>
#include <string.h>
%}

%option noyywrap yylineno

DIGIT       [0-9]
ID          [a-zA-Z_][a-zA-Z0-9_]*
FLOATNUM    ({DIGIT}+\.{DIGIT}*|\.{DIGIT}+)([eE][+-]?{DIGIT}+)?

%%

[ \t\r]+                ;
\n                      ;
"//".*                  ;
"/*"([^*]|\*+[^*/])*\*+"/"  ;
"int"                   { return INT; }
"float"                 { return FLOAT; }
{FLOATNUM}              { yylval.number = strtod(yytext, NULL); return FLOATING; }
{DIGIT}+                { yylval.number = strtod(yytext, NULL); return INTEGER; }
{ID}                    { yylval.str = strdup(yytext); return IDENTIFIER; }
"+"                     { return PLUS; }
"-"                     { return MINUS; }
"*"                     { return MULTIPLY; }
"/"                     { return DIVIDE; }
"%"                     { return MODULO; }
"="                     { return ASSIGN; }
"("                     { return LPAREN; }
")"                     { return RPAREN; }
";"                     { return SEMICOLON; }
.                       { fprintf(stderr, "Lexical error at line %d: invalid character '%s'\n", yylineno, yytext); lexical_errors++; }

%%
