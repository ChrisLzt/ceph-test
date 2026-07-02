#!/bin/bash
hosts=/ior/install/bin/hosts #host file 路径
ior=/ior/install/bin/ior #ior 程序路径
M=16 #并发进程数，客户端数×单客户端cpu核心数
out_path=/mnt/ikcdir/hpc/
mkdir -p "$out_path"
wrfout_gen() {
    mpirun -f $hosts -np $M $ior -w -s `expr 40960 / $M` -a posix -i 48 -m -k -e -t 1M -b 1M -o $out_path/wrfout$1 > perf_wrfout$1.log
} #wrfout生成一天数据基础函数
wrfrst_gen() {
    mpirun -f $hosts -np $M $ior -w -s `expr 4194304 / $M` -a posix -i 1 -m -k -e -t 1M -b 1M -o $out_path/wrfrst$1 > perf_wrfrst$1.log
} #wrfrst生成一天checkpoint数据基础函数

wrfout_gen 1
echo "wrfout 1 done"
wrfrst_gen 1

wrfout_bw=$(grep "write" "perf_wrfout1.log" | tail -n 1 | awk '{print $4}')
wrfrst_bw=$(grep "write" "perf_wrfrst1.log" | tail -n 1 | awk '{print $4}')

echo "wrfout Average Mean(MiB) = $wrfout_bw"
echo "wrfrst Average Mean(MiB) = $wrfrst_bw"
