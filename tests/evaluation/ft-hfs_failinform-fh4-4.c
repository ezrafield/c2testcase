/* CONFIDENTIAL */
/*_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_*/
/*_/_/_/        $DWG-No.:HFS_FAILINFORM-FH4                                               _/_/_/_*/
/*_/_/_/        $Content:油圧回路デバイス故障・正常通知処理（2段LU油圧回路用）            _/_/_/_*/
/*_/_/_/        $Category:FT                                                              _/_/_/_*/
/*_/_/_/        $Date:2024/07/18                                                          _/_/_/_*/
/*_/_/_/        $Design:高松 SCSK                                                         _/_/_/_*/
/*_/_/_/        $Check:                                                                   _/_/_/_*/
/*_/_/_/        $Header:                                                                  _/_/_/_*/
/*_/_/_/        $Copyright(C) 2024  HONDA MOTOR CO., LTD.                                 _/_/_/_*/
/*_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_*/

/*###############################################################################################*/
/*###                                     $INCLUDE FILES$                                    ####*/
/*###############################################################################################*/

#include "hos.h"
#include "def.h"
#include "hgsub.h"
#include "tl_basetypes.h"

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_EXTERN$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
extern VS15 VS15tmpatfact_hf;
extern VFLG VFLGf_hydonfaildetinh_hf;
extern VFLG VFLGf_phydoffsta_tm;
extern VFLG VFLGf_psenofffaildetinh_hf;
extern VFLG VFLGf_psenonfaildetinh_hf;
extern VFLG VFLGf_psenonluhioff_hf;
extern VFLG VFLGf_psenonluoff_hf;
extern VFLG VFLGf_psenonluonrdy_hf;
extern VFLG VFLGf_shaofffaildetinh_hf;
extern VFLG VFLGf_shaonfaildetinh_hf;
extern VFLG VFLGf_shbofffaildetinh_hf;
extern VFLG VFLGf_shbonfaildetinh_hf;
extern VFLG VFLGf_shcofffaildetinh_hf;
extern VFLG VFLGf_shconfaildetinh_hf;
extern VU08 VU08xhydact_hf;
extern VU08 VU08xpsenelefailsta_hf;
extern VU08 VU08xpsenfailsta_hf;
extern VU08 VU08xshaelefailsta_hf;
extern VU08 VU08xshafailsta_hf;
extern VU08 VU08xshahissta_hf;
extern VU08 VU08xshbelefailsta_hf;
extern VU08 VU08xshbfailsta_hf;
extern VU08 VU08xshbhissta_hf;
extern VU08 VU08xshcelefailsta_hf;
extern VU08 VU08xshcfailsta_hf;
extern VU08 VU08xshchissta_hf;

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_PUBLIC$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
#pragma section TM10M
VTIM VTIMthydoffok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtpsenoffok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtpsenoffokhydoff_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtpsenoffokhydon_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtpsenonluhi_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtpsenonlulo_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshaoffok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshaonok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshboffok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshbonok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshcoffok_hf;
#pragma section
#pragma section TM10M
VTIM VTIMtshconok_hf;
#pragma section
VFLG VFLGf_hydfailfsapmt_tm;
VFLG VFLGf_hydoffok_hf;
VFLG VFLGf_hydoffok_tm;
VFLG VFLGf_hydonfail_tm;
VFLG VFLGf_phydcironok_tm;
VFLG VFLGf_psenofffail_tm;
VFLG VFLGf_psenoffok_tm;
VFLG VFLGf_psenonfail_tm;
VFLG VFLGf_shaofffail_tm;
VFLG VFLGf_shaoffok_tm;
VFLG VFLGf_shaonfail_tm;
VFLG VFLGf_shaonok_tm;
VFLG VFLGf_shboffchkok_hf;
VFLG VFLGf_shbofffail_tm;
VFLG VFLGf_shboffok_tm;
VFLG VFLGf_shbonfail_tm;
VFLG VFLGf_shbonok_tm;
VFLG VFLGf_shcoffchkok_hf;
VFLG VFLGf_shcofffail_tm;
VFLG VFLGf_shcoffok_tm;
VFLG VFLGf_shconfail_tm;
VFLG VFLGf_shconok_tm;


/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_STATIC$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
static VFLG X_Sa50_UnitDelay;
static VFLG X_Sa57_UnitDelay;
static VFLG X_Sa64_UnitDelay;
static VFLG X_Sa65_UnitDelay;
static VFLG X_Sa73_UnitDelay;
static VFLG X_Sa78_UnitDelay;
static VFLG X_Sa83_UnitDelay;
static VFLG X_Sa88_UnitDelay;
static VFLG X_Sa93_UnitDelay;
static VFLG X_Sa98_UnitDelay;


/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_EXTERN$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_PUBLIC$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
CS15 XS15tmp_thydoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tplostbl[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tpsenonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshaoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshaonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshboffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshbonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshcoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CS15 XS15tmp_tshconok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15thydoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tplostbl[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tpsenonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshaoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshaonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshboffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshbonok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshcoffok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 XU15tshconok[10] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   
}; 
CU15 CU15tpsenoffokhydoff = 1;
CU15 CU15tpsenoffokhydon = 1;
TBL S_TBLthydoffok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_thydoffok, 
(void *) XU15thydoffok 
}; 
TBL S_TBLtplostbl = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tplostbl, 
(void *) XU15tplostbl 
}; 
TBL S_TBLtpsenonok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tpsenonok, 
(void *) XU15tpsenonok 
}; 
TBL S_TBLtshaoffok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshaoffok, 
(void *) XU15tshaoffok 
}; 
TBL S_TBLtshaonok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshaonok, 
(void *) XU15tshaonok 
}; 
TBL S_TBLtshboffok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshboffok, 
(void *) XU15tshboffok 
}; 
TBL S_TBLtshbonok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshbonok, 
(void *) XU15tshbonok 
}; 
TBL S_TBLtshcoffok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshcoffok, 
(void *) XU15tshcoffok 
}; 
TBL S_TBLtshconok = 
{
   10, 
   SIZE_S15, 
   SIZE_U15, 
(void *) XS15tmp_tshconok, 
(void *) XU15tshconok 
}; 

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_STATIC$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                  $FUNCTION PROTOTYPE$                                   +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
void J_hfs_failinform(void);
void JINIT_hfs_failinform(void);
void JDTCCLR_hfs_failinform(void);

/*************************************************************************************************/
/*************************************************************************************************/
/****         $Function:hfs_failinform                                                        ****/
/****         $Content:油圧回路デバイス故障・正常を通知する                                   ****/
/****                                                                                         ****/
/****         $argument:      なし                                                            ****/
/****         $return value:  なし                                                            ****/
/*************************************************************************************************/
/*************************************************************************************************/
void J_hfs_failinform(void)
{
   
   Int16	Sa11_TSHAOFFOK;	 
   Int16	Sa13_TSHAONOK;	 
   Int16	Sa15_TSHBOFFOK;	 
   Int16	Sa17_TSHBONOK;	 
   Int16	Sa19_TSHCOFFOK;	 
   Int16	Sa21_TSHCONOK;	 
   Int16	Sa4_THYDOFFOK;	 
   Int16	Sa61_out___Non__old___immediate;	 
   Int16	Sa62_out___Non__old___immediate;	 
   Int16	Sa7_TPLOSTBL;	 
   Int16	Sa9_TPSENONOK;	 
   
   FLG	Sa11_LogicalOperator2;	 
   FLG	Sa13_LogicalOperator;	 
   FLG	Sa15_LogicalOperator2;	 
   FLG	Sa15_RelationalOperator2;	 
   FLG	Sa17_LogicalOperator;	 
   FLG	Sa19_LogicalOperator;	 
   FLG	Sa21_LogicalOperator;	 
   FLG	Sa4_LogicalOperator2;	 
   FLG	Sa60_LogicalOperator;	 
   FLG	Sa7_LogicalOperator2;	 
   FLG	Sa7_LogicalOperator3;	 
   FLG	Sa7_LogicalOperator5;	 
   FLG	Sa86_LogicalOperator;	 
   FLG	Sa9_LogicalOperator1;	 
   FLG	Sa9_LogicalOperator3;	 
   
   VFLGf_hydonfail_tm = (Int8) (((!(VFLGf_hydonfaildetinh_hf != 0)) && ((VFLGf_psenonluhioff_hf != 0) || (VFLGf_psenonluonrdy_hf != 0) || (VFLGf_psenonluoff_hf != 0))) || (VFLGf_hydonfail_tm != 0));
   
   Sa4_THYDOFFOK = (Int16) GE_Ipl_tbl(&S_TBLthydoffok, (Int32) VS15tmpatfact_hf);
   
   Sa4_LogicalOperator2 = (Int8) (((VU08xshbhissta_hf == 10) || (VU08xshchissta_hf == 10)) && (!(VFLGf_hydonfaildetinh_hf != 0)));
   
   if (Sa4_LogicalOperator2 != 0) {
      
      if (!(X_Sa50_UnitDelay != 0)) {
         
         VTIMthydoffok_hf = Sa4_THYDOFFOK;
      }
   }
   else {
      
      VTIMthydoffok_hf = Sa4_THYDOFFOK;
   }
   
   X_Sa50_UnitDelay = 1;
   
   if (VFLGf_hydonfail_tm != 0) {
      
      VFLGf_hydoffok_tm = 0;
   }
   else {
      
      if ((Sa4_LogicalOperator2 != 0) && (VTIMthydoffok_hf <= 0)) {
         
         VFLGf_hydoffok_tm = 1;
      }
      else {
         
         VFLGf_hydoffok_tm = VFLGf_hydoffok_hf;
      }
   }
   
   VFLGf_hydoffok_hf = VFLGf_hydoffok_tm;
   
   Sa9_TPSENONOK = (Int16) GE_Ipl_tbl(&S_TBLtpsenonok, (Int32) VS15tmpatfact_hf);
   
   Sa9_LogicalOperator1 = (Int8) ((VU08xhydact_hf == 20) && (!(VFLGf_psenofffaildetinh_hf != 0)));
   
   if (Sa9_LogicalOperator1 != 0) {
      
      if (!(X_Sa65_UnitDelay != 0)) {
         
         VTIMtpsenonlulo_hf = Sa9_TPSENONOK;
      }
   }
   else {
      
      VTIMtpsenonlulo_hf = Sa9_TPSENONOK;
   }
   
   X_Sa65_UnitDelay = 1;
   
   Sa7_TPLOSTBL = (Int16) GE_Ipl_tbl(&S_TBLtplostbl, (Int32) VS15tmpatfact_hf);
   
   Sa7_LogicalOperator5 = (Int8) ((VU08xhydact_hf == 0) && (!(VFLGf_psenonfaildetinh_hf != 0)));
   
   if (Sa7_LogicalOperator5 != 0) {
      
      if (!(X_Sa57_UnitDelay != 0)) {
         
         VTIMtpsenoffok_hf = Sa7_TPLOSTBL;
      }
   }
   else {
      
      VTIMtpsenoffok_hf = Sa7_TPLOSTBL;
   }
   
   X_Sa57_UnitDelay = 1;
   
   Sa60_LogicalOperator = (Int8) ((Sa7_LogicalOperator5 != 0) && (VTIMtpsenoffok_hf <= 0));
   
   Sa7_LogicalOperator2 = (Int8) ((Sa60_LogicalOperator != 0) && (VFLGf_phydoffsta_tm != 0));
   
   if (Sa7_LogicalOperator2 != 0) {
      
      Sa61_out___Non__old___immediate = VTIMtpsenoffokhydoff_hf;
   }
   else {
      
      Sa61_out___Non__old___immediate = CU15tpsenoffokhydoff;
   }
   
   VTIMtpsenoffokhydoff_hf = Sa61_out___Non__old___immediate;
   
   Sa7_LogicalOperator3 = (Int8) ((Sa60_LogicalOperator != 0) && (!(VFLGf_phydoffsta_tm != 0)));
   
   if (Sa7_LogicalOperator3 != 0) {
      
      Sa62_out___Non__old___immediate = VTIMtpsenoffokhydon_hf;
   }
   else {
      
      Sa62_out___Non__old___immediate = CU15tpsenoffokhydon;
   }
   
   VTIMtpsenoffokhydon_hf = Sa62_out___Non__old___immediate;
   
   if (!(VFLGf_shcofffaildetinh_hf != 0)) {
      
      VFLGf_shcofffail_tm = (Int8) (VU08xshcfailsta_hf == 240);
   }
   
   if (!(VFLGf_shaofffaildetinh_hf != 0)) {
      
      VFLGf_shaofffail_tm = (Int8) (VU08xshafailsta_hf == 240);
   }
   
   Sa9_LogicalOperator3 = (Int8) ((VU08xhydact_hf == 30) && (!(VFLGf_psenofffaildetinh_hf != 0)));
   
   if (Sa9_LogicalOperator3 != 0) {
      
      if (!(X_Sa64_UnitDelay != 0)) {
         
         VTIMtpsenonluhi_hf = Sa9_TPSENONOK;
      }
   }
   else {
      
      VTIMtpsenonluhi_hf = Sa9_TPSENONOK;
   }
   
   X_Sa64_UnitDelay = 1;
   
   if (!(VFLGf_psenofffaildetinh_hf != 0)) {
      
      VFLGf_psenofffail_tm = (Int8) (VU08xpsenfailsta_hf == 240);
   }
   
   if (VFLGf_psenofffail_tm != 0) {
      
      VFLGf_phydcironok_tm = 0;
   }
   else {
      
      if (((Sa9_LogicalOperator3 != 0) && (VTIMtpsenonluhi_hf <= 0)) || ((Sa9_LogicalOperator1 != 0) && (VTIMtpsenonlulo_hf <= 0))) {
         
         VFLGf_phydcironok_tm = 1;
      }
   }
   
   if (!(VFLGf_psenonfaildetinh_hf != 0)) {
      
      VFLGf_psenonfail_tm = (Int8) (VU08xpsenfailsta_hf == 230);
   }
   
   if (VFLGf_psenonfail_tm != 0) {
      
      VFLGf_psenoffok_tm = 0;
   }
   else {
      
      if (((Sa7_LogicalOperator2 != 0) && (Sa61_out___Non__old___immediate <= 0)) || ((Sa7_LogicalOperator3 != 0) && (Sa62_out___Non__old___immediate <= 0))) {
         
         VFLGf_psenoffok_tm = 1;
      }
   }
   
   Sa21_TSHCONOK = (Int16) GE_Ipl_tbl(&S_TBLtshconok, (Int32) VS15tmpatfact_hf);
   
   Sa21_LogicalOperator = (Int8) ((VU08xshchissta_hf == 20) && (!(VFLGf_shcofffaildetinh_hf != 0)));
   
   if (Sa21_LogicalOperator != 0) {
      
      if (!(X_Sa98_UnitDelay != 0)) {
         
         VTIMtshconok_hf = Sa21_TSHCONOK;
      }
   }
   else {
      
      VTIMtshconok_hf = Sa21_TSHCONOK;
   }
   
   X_Sa98_UnitDelay = 1;
   
   if (VFLGf_shcofffail_tm != 0) {
      
      VFLGf_shconok_tm = 0;
   }
   else {
      
      if ((Sa21_LogicalOperator != 0) && (VTIMtshconok_hf <= 0)) {
         
         VFLGf_shconok_tm = 1;
      }
   }
   
   Sa19_TSHCOFFOK = (Int16) GE_Ipl_tbl(&S_TBLtshcoffok, (Int32) VS15tmpatfact_hf);
   
   Sa19_LogicalOperator = (Int8) ((VU08xshchissta_hf == 10) && (!(VFLGf_shconfaildetinh_hf != 0)));
   
   if (Sa19_LogicalOperator != 0) {
      
      if (!(X_Sa93_UnitDelay != 0)) {
         
         VTIMtshcoffok_hf = Sa19_TSHCOFFOK;
      }
   }
   else {
      
      VTIMtshcoffok_hf = Sa19_TSHCOFFOK;
   }
   
   X_Sa93_UnitDelay = 1;
   
   if (!(VFLGf_shconfaildetinh_hf != 0)) {
      
      VFLGf_shconfail_tm = (Int8) (VU08xshcfailsta_hf == 230);
   }
   
   VFLGf_shcoffchkok_hf = (Int8) ((Sa19_LogicalOperator != 0) && (VTIMtshcoffok_hf <= 0));
   
   if (VFLGf_shconfail_tm != 0) {
      
      VFLGf_shcoffok_tm = 0;
   }
   else {
      
      if (VFLGf_shcoffchkok_hf != 0) {
         
         VFLGf_shcoffok_tm = 1;
      }
   }
   
   Sa17_TSHBONOK = (Int16) GE_Ipl_tbl(&S_TBLtshbonok, (Int32) VS15tmpatfact_hf);
   
   Sa17_LogicalOperator = (Int8) ((VU08xshbhissta_hf == 20) && (!(VFLGf_shbofffaildetinh_hf != 0)));
   
   if (Sa17_LogicalOperator != 0) {
      
      if (!(X_Sa88_UnitDelay != 0)) {
         
         VTIMtshbonok_hf = Sa17_TSHBONOK;
      }
   }
   else {
      
      VTIMtshbonok_hf = Sa17_TSHBONOK;
   }
   
   X_Sa88_UnitDelay = 1;
   
   if (!(VFLGf_shbofffaildetinh_hf != 0)) {
      
      VFLGf_shbofffail_tm = (Int8) (VU08xshbfailsta_hf == 240);
   }
   
   if (VFLGf_shbofffail_tm != 0) {
      
      VFLGf_shbonok_tm = 0;
   }
   else {
      
      if ((Sa17_LogicalOperator != 0) && (VTIMtshbonok_hf <= 0)) {
         
         VFLGf_shbonok_tm = 1;
      }
   }
   
   Sa15_TSHBOFFOK = (Int16) GE_Ipl_tbl(&S_TBLtshboffok, (Int32) VS15tmpatfact_hf);
   
   Sa15_RelationalOperator2 = (Int8) (VU08xshbhissta_hf == 10);
   
   Sa15_LogicalOperator2 = (Int8) (((Sa15_RelationalOperator2 != 0) || (VU08xshbhissta_hf == 20)) && (!(VFLGf_shbonfaildetinh_hf != 0)));
   
   if (Sa15_LogicalOperator2 != 0) {
      
      if (!(X_Sa83_UnitDelay != 0)) {
         
         VTIMtshboffok_hf = Sa15_TSHBOFFOK;
      }
   }
   else {
      
      VTIMtshboffok_hf = Sa15_TSHBOFFOK;
   }
   
   X_Sa83_UnitDelay = 1;
   
   if (!(VFLGf_shbonfaildetinh_hf != 0)) {
      
      VFLGf_shbonfail_tm = (Int8) (VU08xshbfailsta_hf == 230);
   }
   
   Sa86_LogicalOperator = (Int8) ((Sa15_LogicalOperator2 != 0) && (VTIMtshboffok_hf <= 0));
   
   if (VFLGf_shbonfail_tm != 0) {
      
      VFLGf_shboffok_tm = 0;
   }
   else {
      
      if (Sa86_LogicalOperator != 0) {
         
         VFLGf_shboffok_tm = 1;
      }
   }
   
   Sa13_TSHAONOK = (Int16) GE_Ipl_tbl(&S_TBLtshaonok, (Int32) VS15tmpatfact_hf);
   
   Sa13_LogicalOperator = (Int8) ((VU08xshahissta_hf == 20) && (!(VFLGf_shaofffaildetinh_hf != 0)));
   
   if (Sa13_LogicalOperator != 0) {
      
      if (!(X_Sa78_UnitDelay != 0)) {
         
         VTIMtshaonok_hf = Sa13_TSHAONOK;
      }
   }
   else {
      
      VTIMtshaonok_hf = Sa13_TSHAONOK;
   }
   
   X_Sa78_UnitDelay = 1;
   
   if (VFLGf_shaofffail_tm != 0) {
      
      VFLGf_shaonok_tm = 0;
   }
   else {
      
      if ((Sa13_LogicalOperator != 0) && (VTIMtshaonok_hf <= 0)) {
         
         VFLGf_shaonok_tm = 1;
      }
   }
   
   Sa11_TSHAOFFOK = (Int16) GE_Ipl_tbl(&S_TBLtshaoffok, (Int32) VS15tmpatfact_hf);
   
   Sa11_LogicalOperator2 = (Int8) (((VU08xshahissta_hf == 10) || (VU08xshahissta_hf == 20)) && (!(VFLGf_shaonfaildetinh_hf != 0)));
   
   if (Sa11_LogicalOperator2 != 0) {
      
      if (!(X_Sa73_UnitDelay != 0)) {
         
         VTIMtshaoffok_hf = Sa11_TSHAOFFOK;
      }
   }
   else {
      
      VTIMtshaoffok_hf = Sa11_TSHAOFFOK;
   }
   
   X_Sa73_UnitDelay = 1;
   
   if (!(VFLGf_shaonfaildetinh_hf != 0)) {
      
      VFLGf_shaonfail_tm = (Int8) (VU08xshafailsta_hf == 230);
   }
   
   if (VFLGf_shaonfail_tm != 0) {
      
      VFLGf_shaoffok_tm = 0;
   }
   else {
      
      if ((Sa11_LogicalOperator2 != 0) && (VTIMtshaoffok_hf <= 0)) {
         
         VFLGf_shaoffok_tm = 1;
      }
   }
   
   VFLGf_hydfailfsapmt_tm = (Int8) ((VFLGf_shaonfail_tm != 0) || (VFLGf_shaofffail_tm != 0) || (VFLGf_shbonfail_tm != 0) || (VFLGf_shbofffail_tm != 0) || (VFLGf_shconfail_tm != 0) ||
    (VFLGf_shcofffail_tm != 0) || (VFLGf_psenonfail_tm != 0) || (VFLGf_psenofffail_tm != 0) || (VFLGf_hydonfail_tm != 0) || ((VU08xshaelefailsta_hf == 240) || (VU08xshaelefailsta_hf == 230) ||
    (VU08xshbelefailsta_hf == 240) || (VU08xshbelefailsta_hf == 230) || (VU08xshcelefailsta_hf == 240) || (VU08xshcelefailsta_hf == 230) || (VU08xpsenelefailsta_hf == 240) || (VU08xpsenelefailsta_hf
    == 230)));
   
   VFLGf_shboffchkok_hf = (Int8) ((Sa15_RelationalOperator2 != 0) && (Sa86_LogicalOperator != 0));
}

/*************************************************************************************************/
/****         $Function: hfs_failinform（イニシャル処理）                                     ****/
/****         $Content:  イニシャル処理                                                       ****/
/*************************************************************************************************/
void JINIT_hfs_failinform(void) 
{
   VTIMtshconok_hf = 0x0064;
   VTIMthydoffok_hf = 0x0064;
   VTIMtpsenoffok_hf = 0x0064;
   VTIMtshcoffok_hf = 0x0064;
   VTIMtpsenonluhi_hf = 0x0064;
   VTIMtshaonok_hf = 0x0064;
   VTIMtshboffok_hf = 0x0064;
   VTIMtshaoffok_hf = 0x0064;
   VTIMtshbonok_hf = 0x0064;
   VTIMtpsenonlulo_hf = 0x0064;
   VTIMtpsenoffokhydon_hf = CU15tpsenoffokhydon;
   VTIMtpsenoffokhydoff_hf = CU15tpsenoffokhydoff;
}
/*************************************************************************************************/
/****         $Function: hfs_failinform（テスタＡ処理）                                       ****/
/****         $Content:  DTC クリア処理                                                       ****/
/*************************************************************************************************/
void JDTCCLR_hfs_failinform(void) 
{
   VTIMtshconok_hf = 0x0064;
   VTIMthydoffok_hf = 0x0064;
   VFLGf_psenonfail_tm = 0x0;
   VTIMtpsenoffok_hf = 0x0064;
   VFLGf_shbofffail_tm = 0x0;
   VFLGf_shcoffok_tm = 0x0;
   VTIMtshcoffok_hf = 0x0064;
   VTIMtpsenonluhi_hf = 0x0064;
   VFLGf_shbonfail_tm = 0x0;
   VTIMtshaonok_hf = 0x0064;
   VTIMtshboffok_hf = 0x0064;
   VFLGf_phydcironok_tm = 0x0;
   VFLGf_shbonok_tm = 0x0;
   VTIMtshbonok_hf = 0x0064;
   VFLGf_shboffok_tm = 0x0;
   VFLGf_shaofffail_tm = 0x0;
   VFLGf_psenoffok_tm = 0x0;
   VFLGf_shconok_tm = 0x0;
   VFLGf_hydonfail_tm = 0x0;
   VFLGf_shaoffok_tm = 0x0;
   VFLGf_shcofffail_tm = 0x0;
   VFLGf_psenofffail_tm = 0x0;
   VFLGf_shaonfail_tm = 0x0;
   VFLGf_hydoffok_hf = 0x0;
   VFLGf_shconfail_tm = 0x0;
   VFLGf_shaonok_tm = 0x0;
   VTIMtshaoffok_hf = 0x0064;
   VTIMtpsenonlulo_hf = 0x0064;
   VTIMtpsenoffokhydon_hf = CU15tpsenoffokhydon;
   VTIMtpsenoffokhydoff_hf = CU15tpsenoffokhydoff;
}





/*-----------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------*/
/*---                                   REVISION MANAGEMENT                                   ---*/
/*-----------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------*/
/*---																						  ---*/
/*---   $Rev:	date:		name:		company:	minute:	content:						  ---*/
/*---   $Rev:40	2026/03/06	ManhVo		FS					EAGLE4.1p3	TL4.3p5				  ---*/
/*---																						  ---*/
/*-----------------------------------------------------------------------------------------------*/
/*---
        $Log$
                                                                                              ---*/
/*-----------------------------------------------------------------------------------------------*/

 
