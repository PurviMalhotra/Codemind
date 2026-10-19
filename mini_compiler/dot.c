#include "common.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int node_id = 0;
static FILE *dot_file;

static void label_for(ASTNode *n, char *buf, size_t size) {
    if (!n) { snprintf(buf, size, "null"); return; }
    switch (n->kind) {
        case NODE_PROGRAM: snprintf(buf, size, "Program"); break;
        case NODE_DECL: snprintf(buf, size, "Declaration: %s", n->text ? n->text : ""); break;
        case NODE_ASSIGN: snprintf(buf, size, "Assignment: %s", n->text ? n->text : ""); break;
        case NODE_INT: snprintf(buf, size, "Integer: %.0f", n->number); break;
        case NODE_FLOAT: snprintf(buf, size, "Float: %g", n->number); break;
        case NODE_ID: snprintf(buf, size, "Identifier: %s", n->text ? n->text : ""); break;
        case NODE_BINOP: snprintf(buf, size, "Operator: %s", n->text ? n->text : ""); break;
        case NODE_UNARY: snprintf(buf, size, "Unary: %s", n->text ? n->text : ""); break;
    }
}

static int draw_node(ASTNode *n) {
    if (!n) return -1;
    int id = ++node_id;
    char label[256];
    label_for(n, label, sizeof(label));
    fprintf(dot_file, "  n%d [label=\"%s\"];\n", id, label);

    if (n->left) {
        int child = draw_node(n->left);
        fprintf(dot_file, "  n%d -> n%d;\n", id, child);
    }
    if (n->right) {
        int child = draw_node(n->right);
        fprintf(dot_file, "  n%d -> n%d;\n", id, child);
    }
    if (n->next) {
        int child = draw_node(n->next);
        fprintf(dot_file, "  n%d -> n%d [style=dashed,label=\"next statement\"];\n", id, child);
    }
    return id;
}

void write_dot(ASTNode *program, const char *filename) {
    dot_file = fopen(filename, "w");
    if (!dot_file) { perror(filename); return; }
    node_id = 0;
    fprintf(dot_file, "digraph AST {\n");
    fprintf(dot_file, "  graph [rankdir=TB, bgcolor=\"white\"];\n");
    fprintf(dot_file, "  node [shape=box, style=\"rounded,filled\", fillcolor=\"#e8f0fe\", fontname=\"Arial\"];\n");
    fprintf(dot_file, "  edge [fontname=\"Arial\"];\n");
    draw_node(program);
    fprintf(dot_file, "}\n");
    fclose(dot_file);
}
