(* Content-type: application/vnd.wolfram.mathematica *)

(*** Wolfram Notebook File ***)
(* http://www.wolfram.com/nb *)

(* CreatedBy='Wolfram 14.2' *)

(*CacheID: 234*)
(* Internal cache information:
NotebookFileLineBreakTest
NotebookFileLineBreakTest
NotebookDataPosition[       154,          7]
NotebookDataLength[     27249,        572]
NotebookOptionsPosition[     26851,        558]
NotebookOutlinePosition[     27289,        574]
CellTagsIndexPosition[     27246,        571]
WindowFrame->Normal*)

(* Beginning of Notebook Content *)
Notebook[{
Cell[BoxData[
 RowBox[{
  RowBox[{"(*", 
   RowBox[{
    RowBox[{"Authority", ":", 
     RowBox[{"Signal", " ", "Light", " ", "Press", " ", "Classification"}], ":", 
     RowBox[{"Internal", " ", 
      RowBox[{"Scope", ":", 
       RowBox[{"Visualization", " ", "Only", " ", "Status"}], ":", 
       RowBox[{"Draft", " ", "SIGNAL", " ", "SCOPE"}]}]}]}], "\[LongDash]", 
    RowBox[{"PHASE", " ", "BRAID", " ", "RENDERER", " ", 
     RowBox[{"(", "WL", ")"}], " ", "This", " ", "file", " ", "is", " ", "a", 
     " ", "renderer", " ", 
     RowBox[{"only", ".", "It"}], " ", "draws", " ", "geometry", " ", "from", 
     " ", "supplied", " ", "numeric", " ", 
     RowBox[{"fields", ".", "It"}], " ", "does", " ", "not", " ", "compute", " ",
      "signal", " ", "truth"}], ",", 
    RowBox[{"apply", " ", "thresholds"}], ",", 
    RowBox[{"or", " ", "label", " ", 
     RowBox[{"regimes", "."}]}]}], "*)"}], 
  RowBox[{
  "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}], 
  RowBox[{"(*", 
   RowBox[{"CONFIG", " ", 
    RowBox[{"(", 
     RowBox[{"human", "-", 
      RowBox[{"invoked", " ", "paths", " ", "only"}]}], ")"}]}], "*)"}], 
  RowBox[{
  "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}], 
  RowBox[{
   RowBox[{
    RowBox[{"csvPath", "=", 
     RowBox[{"FileNameJoin", "[", 
      RowBox[{"{", 
       RowBox[{
        RowBox[{"NotebookDirectory", "[", "]"}], 
        ",", "\"\<sample_scope_window.csv\>\""}], "}"}], "]"}]}], ";"}], "\n",
    "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{"Optional", " ", "export", " ", 
     RowBox[{"(", 
      RowBox[{"set", " ", "to", " ", "None", " ", "to", " ", "disable"}], 
      ")"}]}], "*)"}], "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"exportPath", "=", 
     RowBox[{"FileNameJoin", "[", 
      RowBox[{"{", 
       RowBox[{
        RowBox[{"NotebookDirectory", "[", "]"}], 
        ",", "\"\<phase_braid.png\>\""}], "}"}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\[IndentingNewLine]", "\n", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{"LOAD", " ", 
     RowBox[{"(", 
      RowBox[{"CSV", "\[RightArrow]", 
       RowBox[{"Association", " ", "rows"}]}], ")"}]}], "*)"}], 
   "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"data", "=", 
     RowBox[{"Import", "[", 
      RowBox[{"\"\<sample_scope_window.csv\>\"", ",", "\"\<Dataset\>\""}], 
      "]"}]}], ";"}], "\n", "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{
     RowBox[{"Expect", " ", "columns", " ", 
      RowBox[{"like", ":", "t"}]}], ",", "coherence", ",", "phase_spread", ",",
      "buffer_margin", ",", 
     RowBox[{"persistence", " ", 
      RowBox[{"optional", ":", "drift"}]}], ",", "afterglow"}], "*)"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{"rows", "=", 
     RowBox[{"Normal", "[", "data", "]"}]}], ";"}], "\[IndentingNewLine]", 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{"FIELD", " ", "PICKERS", " ", 
     RowBox[{"(", 
      RowBox[{
       RowBox[{"no", " ", "inference"}], ";", 
       RowBox[{"just", " ", "presence", " ", "checks"}]}], ")"}]}], "*)"}], 
   "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{
     RowBox[{"has", "[", "col_", "]"}], ":=", 
     RowBox[{"KeyExistsQ", "[", 
      RowBox[{
       RowBox[{"First", "[", "rows", "]"}], ",", "col"}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{
     RowBox[{"get", "[", "col_", "]"}], ":=", 
     RowBox[{"(", 
      RowBox[{
       RowBox[{
        RowBox[{"Lookup", "[", 
         RowBox[{"#", ",", "col", ",", 
          RowBox[{"Missing", "[", "\"\<NotAvailable\>\"", "]"}]}], "]"}], 
        "&"}], "/@", "rows"}], ")"}]}], ";"}], "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{"t", "=", 
     RowBox[{"get", "[", "\"\<t\>\"", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"coh", "=", 
     RowBox[{"get", "[", "\"\<coherence\>\"", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"ps", "=", 
     RowBox[{"get", "[", "\"\<phase_spread\>\"", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"bm", "=", 
     RowBox[{"get", "[", "\"\<buffer_margin\>\"", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"p", "=", 
     RowBox[{"get", "[", "\"\<persistence\>\"", "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{"dr", "=", 
     RowBox[{"If", "[", 
      RowBox[{
       RowBox[{"has", "[", "\"\<drift\>\"", "]"}], ",", 
       RowBox[{"get", "[", "\"\<drift\>\"", "]"}], ",", 
       RowBox[{"ConstantArray", "[", 
        RowBox[{
         RowBox[{"Missing", "[", "\"\<NotAvailable\>\"", "]"}], ",", 
         RowBox[{"Length", "[", "rows", "]"}]}], "]"}]}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"ag", "=", 
     RowBox[{"If", "[", 
      RowBox[{
       RowBox[{"has", "[", "\"\<afterglow\>\"", "]"}], ",", 
       RowBox[{"get", "[", "\"\<afterglow\>\"", "]"}], ",", 
       RowBox[{"ConstantArray", "[", 
        RowBox[{
         RowBox[{"Missing", "[", "\"\<NotAvailable\>\"", "]"}], ",", 
         RowBox[{"Length", "[", "rows", "]"}]}], "]"}]}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\n", 
   RowBox[{"(*", 
    RowBox[{"BRAID", " ", "GEOMETRY"}], "*)"}], "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{"We", " ", "draw", " ", "three", " ", 
     RowBox[{"strands", ":", 
      RowBox[{"Strand", " ", "A"}], ":", 
      RowBox[{"\"\<coherence\>\"", " ", "mapped", " ", "as", " ", "radius", " ", 
       RowBox[{"(", 
        RowBox[{"already", " ", "present"}], ")"}], " ", "Strand", " ", 
       RowBox[{"B", ":", 
        RowBox[{"\"\<phase_spread\>\"", " ", "mapped", " ", "as", " ", 
         "vertical", " ", "component", " ", 
         RowBox[{"(", 
          RowBox[{"already", " ", "present"}], ")"}], " ", "Strand", " ", 
         "C"}], ":", 
        RowBox[{"\"\<buffer_margin\>\"", " ", "mapped", " ", "as", " ", 
         "radius", " ", 
         RowBox[{"(", 
          RowBox[{"already", " ", "present"}], ")"}], " ", "No", " ", 
         RowBox[{"thresholds", ".", "No"}], " ", 
         RowBox[{"smoothing", ".", "No"}], " ", 
         RowBox[{"resampling", ".", "We"}], " ", "only", " ", "omit", " ", 
         "missing", " ", "values", " ", 
         RowBox[{
          RowBox[{"(", 
           RowBox[{"presentation", " ", "windowing"}], ")"}], "."}]}]}]}]}]}],
     "*)"}], "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"cleanTriples", "=", 
     RowBox[{"Select", "[", 
      RowBox[{
       RowBox[{"Transpose", "[", 
        RowBox[{"{", 
         RowBox[{"t", ",", "coh", ",", "ps", ",", "bm", ",", "p"}], "}"}], 
        "]"}], ",", 
       RowBox[{
        RowBox[{"FreeQ", "[", 
         RowBox[{"#", ",", 
          RowBox[{"Missing", "[", "\"\<NotAvailable\>\"", "]"}]}], "]"}], 
        "&"}]}], "]"}]}], ";"}], "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{"If", "[", 
     RowBox[{
      RowBox[{
       RowBox[{"Length", "[", "cleanTriples", "]"}], "<", "3"}], ",", 
      RowBox[{
       RowBox[{
       "Print", "[", "\"\<Not enough complete rows to render braid.\>\"", 
        "]"}], ";", "\[IndentingNewLine]", 
       RowBox[{"Quit", "[", "]"}], ";"}]}], "]"}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
    RowBox[{"tC", "=", 
     RowBox[{"cleanTriples", "[", 
      RowBox[{"[", 
       RowBox[{"All", ",", "1"}], "]"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"cohC", "=", 
     RowBox[{"cleanTriples", "[", 
      RowBox[{"[", 
       RowBox[{"All", ",", "2"}], "]"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"psC", "=", 
     RowBox[{"cleanTriples", "[", 
      RowBox[{"[", 
       RowBox[{"All", ",", "3"}], "]"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"bmC", "=", 
     RowBox[{"cleanTriples", "[", 
      RowBox[{"[", 
       RowBox[{"All", ",", "4"}], "]"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"pC", "=", 
     RowBox[{"cleanTriples", "[", 
      RowBox[{"[", 
       RowBox[{"All", ",", "5"}], "]"}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{"(*", 
    RowBox[{"Normalize", " ", "time", " ", 
     RowBox[{"to", "[", 
      RowBox[{"0", ",", "1"}], "]"}], " ", "purely", " ", "for", " ", 
     "plotting", " ", "coordinate", " ", "scale"}], "*)"}], "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"t0", "=", 
     RowBox[{"First", "[", "tC", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"t1", "=", 
     RowBox[{"Last", "[", "tC", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"u", "=", 
     RowBox[{"If", "[", 
      RowBox[{
       RowBox[{"t1", "==", "t0"}], ",", 
       RowBox[{"ConstantArray", "[", 
        RowBox[{"0.0", ",", 
         RowBox[{"Length", "[", "tC", "]"}]}], "]"}], ",", 
       RowBox[{
        RowBox[{"(", 
         RowBox[{"tC", "-", "t0"}], ")"}], "/", 
        RowBox[{"(", 
         RowBox[{"t1", "-", "t0"}], ")"}]}]}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{"(*", 
    RowBox[{
    "Map", " ", "persistence", " ", "to", " ", "a", " ", "gentle", " ", 
     "strand", " ", "separation", " ", 
     RowBox[{"(", 
      RowBox[{"purely", " ", "geometric"}], ")"}]}], "*)"}], "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"pMax", "=", 
     RowBox[{"Max", "[", "pC", "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"sep", "=", 
     RowBox[{"If", "[", 
      RowBox[{
       RowBox[{"pMax", "<=", "0"}], ",", 
       RowBox[{"ConstantArray", "[", 
        RowBox[{"0.0", ",", 
         RowBox[{"Length", "[", "pC", "]"}]}], "]"}], ",", 
       RowBox[{"(", 
        RowBox[{"pC", "/", "pMax"}], ")"}]}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", 
   RowBox[{"(*", 
    RowBox[{"Strand", " ", "definitions", " ", 
     RowBox[{"(", 
      RowBox[{"3", "D", " ", "curves"}], ")"}]}], "*)"}], "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"strandA", "=", 
     RowBox[{"Transpose", "[", 
      RowBox[{"{", 
       RowBox[{"u", ",", "cohC", ",", "psC"}], "}"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"strandB", "=", 
     RowBox[{"Transpose", "[", 
      RowBox[{"{", 
       RowBox[{"u", ",", "bmC", ",", "psC"}], "}"}], "]"}]}], ";"}], "\n", 
   RowBox[{
    RowBox[{"strandC", "=", 
     RowBox[{"Transpose", "[", 
      RowBox[{"{", 
       RowBox[{"u", ",", "sep", ",", "psC"}], "}"}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\[IndentingNewLine]", "\n", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", 
   RowBox[{"(*", "RENDER", "*)"}], "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"plt", "=", 
     RowBox[{"Show", "[", 
      RowBox[{
       RowBox[{"{", 
        RowBox[{
         RowBox[{"Graphics3D", "[", 
          RowBox[{"{", 
           RowBox[{"Thick", ",", 
            RowBox[{"Line", "[", "strandA", "]"}]}], "}"}], "]"}], ",", 
         RowBox[{"Graphics3D", "[", 
          RowBox[{"{", 
           RowBox[{"Thick", ",", 
            RowBox[{"Line", "[", "strandB", "]"}]}], "}"}], "]"}], ",", 
         RowBox[{"Graphics3D", "[", 
          RowBox[{"{", 
           RowBox[{"Thick", ",", 
            RowBox[{"Line", "[", "strandC", "]"}]}], "}"}], "]"}]}], "}"}], ",", 
       RowBox[{"Axes", "->", "True"}], ",", 
       RowBox[{"AxesLabel", "->", 
        RowBox[{"{", 
         RowBox[{"\"\<u\>\"", ",", "\"\<radius\>\"", 
          ",", "\"\<phase_spread\>\""}], "}"}]}], ",", 
       RowBox[{"BoxRatios", "->", 
        RowBox[{"{", 
         RowBox[{"2", ",", "1", ",", "1"}], "}"}]}], ",", 
       RowBox[{"PlotRange", "->", "All"}], ",", 
       RowBox[{"ImageSize", "->", "1100"}]}], "]"}]}], ";"}], 
   "\[IndentingNewLine]", "\n", "plt", "\[IndentingNewLine]", 
   "\[IndentingNewLine]", "\n", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", 
   RowBox[{"(*", 
    RowBox[{"OPTIONAL", " ", "EXPORT", " ", 
     RowBox[{"(", 
      RowBox[{"static", " ", "artifact", " ", "only"}], ")"}]}], "*)"}], 
   "\[IndentingNewLine]", 
   RowBox[{
   "(*", "\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\
\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]\[HorizontalLine]", "*)"}],
    "\[IndentingNewLine]", "\[IndentingNewLine]", 
   RowBox[{
    RowBox[{"If", "[", 
     RowBox[{
      RowBox[{"exportPath", "=!=", "None"}], ",", 
      RowBox[{
       RowBox[{"Export", "[", 
        RowBox[{"exportPath", ",", "plt"}], "]"}], ";", "\[IndentingNewLine]", 
       RowBox[{"Print", "[", 
        RowBox[{"\"\<Exported: \>\"", ",", "exportPath"}], "]"}], ";"}]}], 
     "]"}], ";"}], "\n"}]}]], "Input",
 CellChangeTimes->{{3.9783634068384132`*^9, 3.9783634068384132`*^9}, {
  3.9783651256553574`*^9, 
  3.978365126484947*^9}},ExpressionUUID->"0368ddd8-a789-b440-a3fc-\
48c9e68aeb61"]
},
WindowSize->{582.6, 655.1999999999999},
WindowMargins->{{198.6, Automatic}, {34.200000000000045`, Automatic}},
FrontEndVersion->"14.2 for Microsoft Windows (64-bit) (December 26, 2024)",
StyleDefinitions->"Default.nb",
ExpressionUUID->"60a26241-1c60-1844-8963-ac84fe9bdfbf"
]
(* End of Notebook Content *)

(* Internal cache information *)
(*CellTagsOutline
CellTagsIndex->{}
*)
(*CellTagsIndex
CellTagsIndex->{}
*)
(*NotebookFileOutline
Notebook[{
Cell[554, 20, 26293, 536, 2102, "Input",ExpressionUUID->"0368ddd8-a789-b440-a3fc-48c9e68aeb61"]
}
]
*)

