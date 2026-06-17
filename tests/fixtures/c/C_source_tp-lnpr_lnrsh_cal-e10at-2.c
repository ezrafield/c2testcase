/* CONFIDENTIAL */
/*_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_*/
/*_/_/_/        $DWG-No.:LNPR_LNRSH_CAL-E10AT                                             _/_/_/_*/
/*_/_/_/        $Content:REV_RATIO_CAL                                                    _/_/_/_*/
/*_/_/_/        $Category:TP                                                              _/_/_/_*/
/*_/_/_/        $Date:2022/07/06                                                          _/_/_/_*/
/*_/_/_/        $Design:��� �_�R                                                         _/_/_/_*/
/*_/_/_/        $Check:                                                                   _/_/_/_*/
/*_/_/_/        $Header:                                                                  _/_/_/_*/
/*_/_/_/        $Copyright(C) 2022  HONDA MOTOR CO., LTD.                                 _/_/_/_*/
/*_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_/_*/

/*###############################################################################################*/
/*###                                     $INCLUDE FILES$                                    ####*/
/*###############################################################################################*/

#include "hos.h"
#include "def.h"
#include "hgsub.h"
#include "tl_basetypes.h"
#include "hgsfloat.h"

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_EXTERN$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
extern VF24 VF24bgratiof_s;
extern VU16 VU16rsh;
extern VFLG VFLGf_nckok;
extern VFLG VFLGf_nmkok;
extern VU08 VU08sc_gagb;

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_PUBLIC$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
VF24 AF24ln_bgratiofi_s[3];
VF24 AF24ln_bgratiofo_s[3];
VU16 VU16ln_rsh;
VU16 VU16ln_rshtp_ncsnms;


/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $RAM_STATIC$                                        +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/


/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_EXTERN$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_PUBLIC$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
CU16 XU16ln_rshtp[12] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 
    11, 12
   
}; 
CU16 XU16ln_rshtp_ncsnms[12] = 
{
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 
    11, 12
   
}; 
CS15 XS15ln_bgratiofd12[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd23[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd24[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd34[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd35[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd45[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd46[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd56[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd57[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd67[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd68[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd78[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd79[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd89[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd8a[2] = 
{
    1, 2
   
}; 
CS15 XS15ln_bgratiofd9a[2] = 
{
    1, 2
   
}; 
CU16 XU16ln_bgratiofc12[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc23[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc24[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc34[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc35[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc45[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc46[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc56[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc57[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc67[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc68[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc78[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc79[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc89[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc8a[3] = 
{
    1, 2, 3
   
}; 
CU16 XU16ln_bgratiofc9a[3] = 
{
    1, 2, 3
   
}; 
CFLG CFLGrssw_lnrshfil12 = 1;
CFLG CFLGrssw_lnrshfil23 = 1;
CFLG CFLGrssw_lnrshfil24 = 1;
CFLG CFLGrssw_lnrshfil34 = 1;
CFLG CFLGrssw_lnrshfil35 = 1;
CFLG CFLGrssw_lnrshfil45 = 1;
CFLG CFLGrssw_lnrshfil46 = 1;
CFLG CFLGrssw_lnrshfil56 = 1;
CFLG CFLGrssw_lnrshfil57 = 1;
CFLG CFLGrssw_lnrshfil67 = 1;
CFLG CFLGrssw_lnrshfil68 = 1;
CFLG CFLGrssw_lnrshfil78 = 1;
CFLG CFLGrssw_lnrshfil79 = 1;
CFLG CFLGrssw_lnrshfil89 = 1;
CFLG CFLGrssw_lnrshfil8a = 1;
CFLG CFLGrssw_lnrshfil9a = 1;
TBL S_TBLln_rshtp = 
{
   12, 
   SIZE_U16, 
   SIZE_U16, 
(void *) XU16ln_rshtp_ncsnms, 
(void *) XU16ln_rshtp 
}; 

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                     $DATA_STATIC$                                       +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/

/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++                                  $FUNCTION PROTOTYPE$                                   +++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
/*+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++*/
void J_tplnpr_lnrsh_cal(void);

/*************************************************************************************************/
/*************************************************************************************************/
/****         $Function:tplnpr_lnrsh_cal                                                      ****/
/****         $Content:�M�����V�I�̎Z�o(UP�p)                                                 ****/
/****                                                                                         ****/
/****         $argument:      �Ȃ�                                                            ****/
/****         $return value:  �Ȃ�                                                            ****/
/*************************************************************************************************/
/*************************************************************************************************/
void J_tplnpr_lnrsh_cal(void)
{
   
   Float32	Sa2_bgratiof_s_;
   
   Float32	Sa4_Sum2;
   
   UInt16 Sa7_out___Nona__ld___immediate1[3]; 
   Int16 Sa8_out___Nona__ld___immediate1[2]; 
   
   FLG	Sa3_out___Nona__ld___immediate1;	 
   
   Float32	Aux_F32;
   Float32	Aux_F32_a;
   
   Aux_F32 = AF24ln_bgratiofi_s[1];
   
   if (VU08sc_gagb == 18) {
      
      Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc12[0];
      Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc12[1];
      Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc12[2];
   }
   else {
      
      if (VU08sc_gagb == 35) {
         
         Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc23[0];
         Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc23[1];
         Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc23[2];
      }
      else {
         
         if (VU08sc_gagb == 52) {
            
            Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc34[0];
            Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc34[1];
            Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc34[2];
         }
         else {
            
            if (VU08sc_gagb == 69) {
               
               Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc45[0];
               Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc45[1];
               Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc45[2];
            }
            else {
               
               if (VU08sc_gagb == 86) {
                  
                  Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc56[0];
                  Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc56[1];
                  Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc56[2];
               }
               else {
                  
                  if (VU08sc_gagb == 103) {
                     
                     Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc67[0];
                     Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc67[1];
                     Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc67[2];
                  }
                  else {
                     
                     if (VU08sc_gagb == 120) {
                        
                        Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc78[0];
                        Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc78[1];
                        Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc78[2];
                     }
                     else {
                        
                        if (VU08sc_gagb == 137) {
                           
                           Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc89[0];
                           Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc89[1];
                           Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc89[2];
                        }
                        else {
                           
                           if (VU08sc_gagb == 154) {
                              
                              Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc9a[0];
                              Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc9a[1];
                              Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc9a[2];
                           }
                           else {
                              
                              if (VU08sc_gagb == 36) {
                                 
                                 Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc24[0];
                                 Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc24[1];
                                 Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc24[2];
                              }
                              else {
                                 
                                 if (VU08sc_gagb == 53) {
                                    
                                    Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc35[0];
                                    Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc35[1];
                                    Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc35[2];
                                 }
                                 else {
                                    
                                    if (VU08sc_gagb == 70) {
                                       
                                       Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc46[0];
                                       Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc46[1];
                                       Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc46[2];
                                    }
                                    else {
                                       
                                       if (VU08sc_gagb == 87) {
                                          
                                          Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc57[0];
                                          Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc57[1];
                                          Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc57[2];
                                       }
                                       else {
                                          
                                          if (VU08sc_gagb == 104) {
                                             
                                             Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc68[0];
                                             Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc68[1];
                                             Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc68[2];
                                          }
                                          else {
                                             
                                             if (VU08sc_gagb == 121) {
                                                
                                                Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc79[0];
                                                Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc79[1];
                                                Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc79[2];
                                             }
                                             else {
                                                
                                                if (VU08sc_gagb == 138) {
                                                   
                                                   Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc8a[0];
                                                   Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc8a[1];
                                                   Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc8a[2];
                                                }
                                                else {
                                                   
                                                   Sa7_out___Nona__ld___immediate1[0] = XU16ln_bgratiofc12[0];
                                                   Sa7_out___Nona__ld___immediate1[1] = XU16ln_bgratiofc12[1];
                                                   Sa7_out___Nona__ld___immediate1[2] = XU16ln_bgratiofc12[2];
                                                }
                                             }
                                          }
                                       }
                                    }
                                 }
                              }
                           }
                        }
                     }
                  }
               }
            }
         }
      }
   }
   
   Sa2_bgratiof_s_ = VF24bgratiof_s;
   
   if (Sa2_bgratiof_s_ > 8.F) {
      
      AF24ln_bgratiofi_s[1] = 8.F;
   }
   else {
      if (Sa2_bgratiof_s_ < 0.F) {
         
         AF24ln_bgratiofi_s[1] = 0.F;
      }
      else {
         
         AF24ln_bgratiofi_s[1] = Sa2_bgratiof_s_;
      }
   }
   
   Aux_F32_a = AF24ln_bgratiofo_s[1];
   
   if (VU08sc_gagb == 18) {
      
      Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd12[0];
      Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd12[1];
   }
   else {
      
      if (VU08sc_gagb == 35) {
         
         Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd23[0];
         Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd23[1];
      }
      else {
         
         if (VU08sc_gagb == 52) {
            
            Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd34[0];
            Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd34[1];
         }
         else {
            
            if (VU08sc_gagb == 69) {
               
               Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd45[0];
               Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd45[1];
            }
            else {
               
               if (VU08sc_gagb == 86) {
                  
                  Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd56[0];
                  Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd56[1];
               }
               else {
                  
                  if (VU08sc_gagb == 103) {
                     
                     Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd67[0];
                     Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd67[1];
                  }
                  else {
                     
                     if (VU08sc_gagb == 120) {
                        
                        Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd78[0];
                        Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd78[1];
                     }
                     else {
                        
                        if (VU08sc_gagb == 137) {
                           
                           Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd89[0];
                           Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd89[1];
                        }
                        else {
                           
                           if (VU08sc_gagb == 154) {
                              
                              Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd9a[0];
                              Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd9a[1];
                           }
                           else {
                              
                              if (VU08sc_gagb == 36) {
                                 
                                 Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd24[0];
                                 Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd24[1];
                              }
                              else {
                                 
                                 if (VU08sc_gagb == 53) {
                                    
                                    Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd35[0];
                                    Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd35[1];
                                 }
                                 else {
                                    
                                    if (VU08sc_gagb == 70) {
                                       
                                       Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd46[0];
                                       Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd46[1];
                                    }
                                    else {
                                       
                                       if (VU08sc_gagb == 87) {
                                          
                                          Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd57[0];
                                          Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd57[1];
                                       }
                                       else {
                                          
                                          if (VU08sc_gagb == 104) {
                                             
                                             Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd68[0];
                                             Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd68[1];
                                          }
                                          else {
                                             
                                             if (VU08sc_gagb == 121) {
                                                
                                                Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd79[0];
                                                Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd79[1];
                                             }
                                             else {
                                                
                                                if (VU08sc_gagb == 138) {
                                                   
                                                   Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd8a[0];
                                                   Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd8a[1];
                                                }
                                                else {
                                                   
                                                   Sa8_out___Nona__ld___immediate1[0] = XS15ln_bgratiofd12[0];
                                                   Sa8_out___Nona__ld___immediate1[1] = XS15ln_bgratiofd12[1];
                                                }
                                             }
                                          }
                                       }
                                    }
                                 }
                              }
                           }
                        }
                     }
                  }
               }
            }
         }
      }
   }
   
   Sa4_Sum2 = ((AF24ln_bgratiofi_s[2] * (((Float32) Sa7_out___Nona__ld___immediate1[0]) * 1.52587890625e-05F)) + (Aux_F32 * (((Float32) Sa7_out___Nona__ld___immediate1[1]) * 1.52587890625e-05F)) +
    (AF24ln_bgratiofi_s[1] * (((Float32) Sa7_out___Nona__ld___immediate1[2]) * 1.52587890625e-05F))) - ((Aux_F32_a * (((Float32) Sa8_out___Nona__ld___immediate1[1]) * 6.103515625e-05F)) +
    (AF24ln_bgratiofo_s[2] * (((Float32) Sa8_out___Nona__ld___immediate1[0]) * 6.103515625e-05F)));
   
   if (Sa4_Sum2 > 8.F) {
      
      AF24ln_bgratiofo_s[1] = 8.F;
   }
   else {
      if (Sa4_Sum2 < 0.F) {
         
         AF24ln_bgratiofo_s[1] = 0.F;
      }
      else {
         
         AF24ln_bgratiofo_s[1] = Sa4_Sum2;
      }
   }
   
   {
      VU16ln_rshtp_ncsnms = GE_Lmt_F24toU16((AF24ln_bgratiofo_s[1] * 8192.F));
   }
   
   AF24ln_bgratiofi_s[0] = AF24ln_bgratiofi_s[1];
   AF24ln_bgratiofi_s[2] = Aux_F32;
   
   AF24ln_bgratiofo_s[0] = AF24ln_bgratiofo_s[1];
   AF24ln_bgratiofo_s[2] = Aux_F32_a;
   
   if (VU08sc_gagb == 18) {
      
      Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil12;
   }
   else {
      
      if (VU08sc_gagb == 35) {
         
         Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil23;
      }
      else {
         
         if (VU08sc_gagb == 52) {
            
            Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil34;
         }
         else {
            
            if (VU08sc_gagb == 69) {
               
               Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil45;
            }
            else {
               
               if (VU08sc_gagb == 86) {
                  
                  Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil56;
               }
               else {
                  
                  if (VU08sc_gagb == 103) {
                     
                     Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil67;
                  }
                  else {
                     
                     if (VU08sc_gagb == 120) {
                        
                        Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil78;
                     }
                     else {
                        
                        if (VU08sc_gagb == 137) {
                           
                           Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil89;
                        }
                        else {
                           
                           if (VU08sc_gagb == 154) {
                              
                              Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil9a;
                           }
                           else {
                              
                              if (VU08sc_gagb == 36) {
                                 
                                 Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil24;
                              }
                              else {
                                 
                                 if (VU08sc_gagb == 53) {
                                    
                                    Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil35;
                                 }
                                 else {
                                    
                                    if (VU08sc_gagb == 70) {
                                       
                                       Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil46;
                                    }
                                    else {
                                       
                                       if (VU08sc_gagb == 87) {
                                          
                                          Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil57;
                                       }
                                       else {
                                          
                                          if (VU08sc_gagb == 104) {
                                             
                                             Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil68;
                                          }
                                          else {
                                             
                                             if (VU08sc_gagb == 121) {
                                                
                                                Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil79;
                                             }
                                             else {
                                                
                                                if (VU08sc_gagb == 138) {
                                                   
                                                   Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil8a;
                                                }
                                                else {
                                                   
                                                   Sa3_out___Nona__ld___immediate1 = CFLGrssw_lnrshfil12;
                                                }
                                             }
                                          }
                                       }
                                    }
                                 }
                              }
                           }
                        }
                     }
                  }
               }
            }
         }
      }
   }
   
   if (Sa3_out___Nona__ld___immediate1 != 0) {
      
      if (VFLGf_nmkok != 0) {
         
         VU16ln_rsh = (UInt16) GE_Ipl_tbl(&S_TBLln_rshtp, (Int32) VU16ln_rshtp_ncsnms);
      }
      else {
         
         if (VFLGf_nckok != 0) {
            
            VU16ln_rsh = 0;
         }
         else {
            
            VU16ln_rsh = 65535 ;
         }
      }
   }
   else {
      
      VU16ln_rsh = VU16rsh;
   }
}






/*-----------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------*/
/*---                                   REVISION MANAGEMENT                                   ---*/
/*-----------------------------------------------------------------------------------------------*/
/*-----------------------------------------------------------------------------------------------*/

/*-----------------------------------------------------------------------------------------------*/
/*---																						  ---*/
/*---   $Rev:	date:		name:		company:	minute:	content:						  ---*/
/*---   $Rev:20	2026/02/24	TuNCH	    FS					EAGLE4.1p3	TL4.3p5				  ---*/
/*---																						  ---*/
/*-----------------------------------------------------------------------------------------------*/
/*---
        $Log$
                                                                                              ---*/
/*-----------------------------------------------------------------------------------------------*/

 
