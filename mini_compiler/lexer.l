%{
#include "common.h"
#include "y.tab.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

FILE *token_trace = NULL;
static int traced(int token, const char *name) {
    if (token_trace) fprintf(token_trace, "%d\t%s\t%s\n", yylineno, name, yytext);
    return token;
}
#define RETURN(token) return traced(token, #token)
#define KEYWORD(token) yylval.line = yylineno; return traced(token, #token)
static void literal(double value) {
    yylval.literal.value = value;
    yylval.literal.line = yylineno;
    if (!isfinite(value)) {
        fprintf(stderr, "Lexical error at line %d: numeric literal is out of range.\n", yylineno);
        lexical_errors++;
    }
}
%}

%option noyywrap yylineno noinput nounput
%x COMMENT

DIGIT       [0-9]
ID          [a-zA-Z_][a-zA-Z0-9_]*
FLOATNUM    (({DIGIT}+\.{DIGIT}*|\.{DIGIT}+)([eE][+-]?{DIGIT}+)?|{DIGIT}+[eE][+-]?{DIGIT}+)

%%

[ \t\r\n]+             ;
"//".*                 ;
"/*"                   { BEGIN(COMMENT); }
<COMMENT>"*/"          { BEGIN(INITIAL); }
<COMMENT>[^*\n]+        ;
<COMMENT>"*"           ;
<COMMENT>\n            ;
<COMMENT><<EOF>>        { fprintf(stderr,"Lexical error at line %d: unterminated comment.\n",yylineno); lexical_errors++; BEGIN(INITIAL); return 0; }
"int"                  { KEYWORD(INT); }
"float"                { KEYWORD(FLOAT); }
"if"                   { KEYWORD(IF); }
"else"                 { KEYWORD(ELSE); }
"while"                { KEYWORD(WHILE); }
{FLOATNUM}             { literal(strtod(yytext,NULL)); RETURN(FLOATING); }
{DIGIT}+               { literal(strtod(yytext,NULL)); RETURN(INTEGER); }
{ID}                   { if (yyleng > 63) { fprintf(stderr,"Lexical error at line %d: identifier exceeds 63 characters.\n",yylineno); lexical_errors++; } yylval.name.text = strdup(yytext); yylval.name.line = yylineno; RETURN(IDENTIFIER); }
"&&"                   { RETURN(AND); }
"||"                   { RETURN(OR); }
"=="                   { RETURN(EQ); }
"!="                   { RETURN(NE); }
"<="                   { RETURN(LE); }
">="                   { RETURN(GE); }
"<"                    { RETURN(LT); }
">"                    { RETURN(GT); }
"!"                    { RETURN(NOT); }
"+"                    { RETURN(PLUS); }
"-"                    { RETURN(MINUS); }
"*"                    { RETURN(MULTIPLY); }
"/"                    { RETURN(DIVIDE); }
"%"                    { RETURN(MODULO); }
"="                    { RETURN(ASSIGN); }
"("                    { RETURN(LPAREN); }
")"                    { RETURN(RPAREN); }
"{"                    { KEYWORD(LBRACE); }
"}"                    { RETURN(RBRACE); }
";"                    { RETURN(SEMICOLON); }
.                      { fprintf(stderr,"Lexical error at line %d: invalid character '%s'\n",yylineno,yytext); lexical_errors++; }

%%
